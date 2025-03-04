from flask import (
    Flask, redirect, render_template, make_response, request, flash, jsonify, send_file
)
from contacts_model import Contact, Archiver
import time

Contact.load_db()

# ========================================================
# Flask App
# ========================================================

app = Flask(__name__)

app.secret_key = b'hypermedia rocks'

HTML_MIME = 'text/html'
HXML_MIME = 'application/vnd.hyperview+xml'

def render_to_response(html_template_name, hxml_template_name, *args, **kwargs):
    content = render_template(hxml_template_name, *args, **kwargs)
    response = make_response(content)
    response.headers['Content-Type'] = HXML_MIME
    return response

# def render_to_response(html_template_name, hxml_template_name, *args, **kwargs):
#     response_type = request.accept_mimetypes.best_match([HTML_MIME, HXML_MIME], default=HTML_MIME)
#     template_name = hxml_template_name if response_type == HXML_MIME else html_template_name
#     content = render_template(template_name, *args, **kwargs)
#     response = make_response(content)
#     response.headers['Content-Type'] = response_type
#     return response

@app.route("/")
def index():
    return redirect("/contacts")

@app.route("/contacts")
def contacts():
    search = request.args.get("q")
    page = int(request.args.get("page", 1))
    rows_only = request.args.get("rows_only") == "true"
    if search:
        contacts_set = Contact.search(search)
        return render_to_response("rows.html", "hv/rows.xml", contacts=contacts_set, page=page)
    else:
        contacts_set = Contact.all(page)
    template_type = "rows" if rows_only else "index"
    return render_to_response(template_type + ".html", "hv/"+template_type+".xml", contacts=contacts_set, page=page, archiver=Archiver.get())


@app.route("/contacts/archive", methods=["POST"])
def start_archive():
    archiver = Archiver.get()
    archiver.run()
    return render_template("archive_ui.html", archiver=archiver)


@app.route("/contacts/archive", methods=["GET"])
def archive_status():
    archiver = Archiver.get()
    return render_template("archive_ui.html", archiver=archiver)


@app.route("/contacts/archive/file", methods=["GET"])
def archive_content():
    archiver = Archiver.get()
    return send_file(archiver.archive_file(), "archive.json", as_attachment=True)


@app.route("/contacts/archive", methods=["DELETE"])
def reset_archive():
    archiver = Archiver.get()
    archiver.reset()
    return render_template("archive_ui.html", archiver=archiver)


@app.route("/contacts/count")
def contacts_count():
    count = Contact.count()
    return "(" + str(count) + " total Contacts)"


@app.route("/contacts/new", methods=['GET'])
def contacts_new_get():
    return render_to_response("new.html", "hv/new.xml", contact=Contact())


@app.route("/contacts/new", methods=['POST'])
def contacts_new():
    c = Contact(None, request.form['first_name'], request.form['last_name'], request.form['phone'],
                request.form['email'])
    if c.save():
        flash("Created New Contact!")
        response_type = request.accept_mimetypes.best_match([HTML_MIME, HXML_MIME], default=HTML_MIME)
        if response_type == HXML_MIME:
            return render_to_response('', 'hv/form_fields.xml', saved=True)
        else:
            return redirect("/contacts")
    else:
        return render_to_response("new.html", "hv/form_fields.xml", contact=c)


@app.route("/contacts/<contact_id>")
def contacts_view(contact_id=0):
    contact = Contact.find(contact_id)
    return render_to_response("show.html", "hv/show.xml", contact=contact)


@app.route("/contacts/<contact_id>/edit", methods=["GET"])
def contacts_edit_get(contact_id=0):
    contact = Contact.find(contact_id)
    return render_to_response("edit.html", "hv/edit.xml", contact=contact)


@app.route("/contacts/<contact_id>/edit", methods=["POST"])
def contacts_edit_post(contact_id=0):
    c = Contact.find(contact_id)
    c.update(request.form['first_name'], request.form['last_name'], request.form['phone'], request.form['email'])
    if c.save():
        flash("Updated Contact!")
        response_type = request.accept_mimetypes.best_match([HTML_MIME, HXML_MIME], default=HTML_MIME)
        if response_type == HXML_MIME:
            return render_to_response('', 'hv/form_fields.xml', contact=c, saved=True)
        else:
            return redirect("/contacts/" + str(contact_id))
    else:
        return render_to_response("edit.html", "hv/form_fields.xml", contact=c)


@app.route("/contacts/<contact_id>/email", methods=["GET"])
def contacts_email_get(contact_id=0):
    c = Contact.find(contact_id)
    c.email = request.args.get('email')
    c.validate()
    return c.errors.get('email') or ""


@app.route("/contacts/<contact_id>", methods=["POST"])
def contacts_delete(contact_id=0):
    contact = Contact.find(contact_id)
    contact.delete()
    if request.headers.get('HX-Trigger') == 'delete-btn':
        flash("Deleted Contact!")
        response_type = request.accept_mimetypes.best_match([HTML_MIME, HXML_MIME], default=HTML_MIME)
        if response_type == HXML_MIME:
            return render_to_response('', 'hv/deleted.xml')
        else:
            return redirect("/contacts", 303)
    else:
        return ""


@app.route("/contacts", methods=["DELETE"])
def contacts_delete_all():
    page = 1
    contact_ids = list(map(int, request.form.getlist("selected_contact_ids")))
    for contact_id in contact_ids:
        contact = Contact.find(contact_id)
        contact.delete()
    flash("Deleted Contacts!")
    contacts_set = Contact.all(page)
    return render_template("index.html", contacts=contacts_set)


# ===========================================================
# JSON Data API
# ===========================================================

@app.route("/api/v1/contacts", methods=["GET"])
def json_contacts():
    contacts_set = Contact.all()
    return {"contacts": [c.__dict__ for c in contacts_set]}


@app.route("/api/v1/contacts", methods=["POST"])
def json_contacts_new():
    c = Contact(None, request.form.get('first_name'), request.form.get('last_name'), request.form.get('phone'),
                request.form.get('email'))
    if c.save():
        return c.__dict__
    else:
        return {"errors": c.errors}, 400


@app.route("/api/v1/contacts/<contact_id>", methods=["GET"])
def json_contacts_view(contact_id=0):
    contact = Contact.find(contact_id)
    return contact.__dict__


@app.route("/api/v1/contacts/<contact_id>", methods=["PUT"])
def json_contacts_edit(contact_id):
    c = Contact.find(contact_id)
    c.update(request.form['first_name'], request.form['last_name'], request.form['phone'], request.form['email'])
    if c.save():
        return c.__dict__
    else:
        return {"errors": c.errors}, 400


@app.route("/api/v1/contacts/<contact_id>", methods=["DELETE"])
def json_contacts_delete(contact_id=0):
    contact = Contact.find(contact_id)
    contact.delete()
    return jsonify({"success": True})


if __name__ == "__main__":
    app.run()
