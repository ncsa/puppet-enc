from flask import Flask, request, abort, Response
from flask_httpauth import HTTPBasicAuth
import os
from time import strftime
from werkzeug.security import generate_password_hash, check_password_hash
import yaml

_hosts = yaml.safe_load(open("data/hosts.yaml"))
_users = yaml.safe_load(open("data/users.yaml"))
_groups = yaml.safe_load(open("data/groups.yaml"))

app = Flask(__name__)
auth = HTTPBasicAuth()


def make_response(data):
    """Create yaml response."""
    resp = Response(response=yaml.dump(data), status=200,  mimetype="text/yaml")
    # resp.headers['Access-Control-Allow-Origin'] = '*'
    return resp


def save_data(what, key, value):
    """Save value to the file, and return respone with value."""
    if what == "users":
        data = _users
    elif what == "hosts":
        data = _hosts
    elif what == "groups":
        data = _groups
    else:
        abort(500)
        data = {}

    if value:
        data[key] = value
    else:
        del data[key]
    with open(os.path.join("data", f"{what}.yaml"), "w") as fp:
        yaml.dump(data, fp)
    return make_response(value)


@auth.verify_password
def verify_password(username, password):
    """Check username/password, return username if found."""
    if username in _users and check_password_hash(_users.get(username)["password"], password):
        return username


@auth.get_user_roles
def get_user_roles(username):
    """Return list of roles for the user"""
    if username in _users:
        return _users.get(username)["roles"]


# ======================================================================


@app.after_request
def after_request(response):
    if "/healthz" != request.path:
        # 127.0.0.1 - Scott [10/Dec/2019:13:55:36 -0700] "GET /server-status HTTP/1.1" 200 2326
        logline = f"{request.remote_addr} -"
        if auth.current_user():
            logline = logline + f" {auth.current_user()}"
        else:
            logline = logline + " -"
        logline = logline + strftime(' [%Y/%b/%d:%H:%M:%S]')
        logline = logline + f' "{request.method} {request.path} {request.environ["SERVER_PROTOCOL"]}"'
        logline = logline + f" {response.status_code} {response.content_length}"
        print(logline)
    return response

# ======================================================================


@app.route("/healthz")
def root():
    return "OK"


# ======================================================================


@app.route("/hosts", methods=['GET'])
@auth.login_required(role=['admin', 'user', 'viewer'])
def list_hosts():
    return make_response(list(_hosts.keys()))


@app.route("/hosts/<fqdn>", methods=['GET'])
@auth.login_required(role=['admin', 'user', 'viewer'])
def get_host(fqdn):
    host = _hosts.get(fqdn)
    if host:
        return make_response(host)

    for (k, v) in _groups.items():
        if k == "default":
            continue
        for h in v['hosts']:
            if fqdn.startswith(h):
                host = v.copy()
                del host['hosts']
                return make_response(host)

    v = _groups.get("default")
    if v:
        host = v.copy()
        del host['hosts']
        return make_response(host)

    return make_response(None)


@app.route("/hosts", methods=['POST'])
@auth.login_required(role=['admin', 'user'])
def add_host():
    """Add a new host (fqdn) with specified data (yaml format)"""
    fqdn = request.form.get("fqdn")
    if not fqdn:
        abort(400)
    data = request.form.get("data")
    if not data:
        abort(400)
    return save_data("hosts", fqdn, yaml.safe_load(data))


@app.route("/hosts/<fqdn>", methods=['PUT'])
@auth.login_required(role=['admin', 'user'])
def update_host(fqdn):
    host = _hosts.get(fqdn)
    if not host:
        abort(404)
    for k in request.form.keys():
        if k == "fqdn":
            continue
        if k == "environment":
            host[k] = request.form.get(k)
        elif k == "classes":
            for v in request.form.getlist(k):
                if v.startswith("-"):
                    if v[:1] in host["classes"]:
                        del host["classes"][v[:1]]
                elif v not in host["classes"]:
                    host["classes"][v] = None
        else:
            if isinstance(host["parameters"].get(k, None), list):
                for v in request.form.getlist(k):
                    if v.startswith("-"):
                        if v[:1] in host["parameters"][k]:
                            host["parameters"][k].remove(v[:1])
                    elif v not in host["parameters"][k]:
                        host["parameters"][k].append(v)
            else:
                v = request.form.get(k)
                if v.startswith("-"):
                    if k in host["parameters"] and v[:1] == host["parameters"][k]:
                        del host["parameters"][k]
                else:
                    host["parameters"][k] = v

    return save_data("hosts", fqdn, host)


@app.route("/hosts/<fqdn>", methods=['DELETE'])
@auth.login_required(role=['admin'])
def delete_host(fqdn):
    if fqdn not in _hosts:
        abort(404)
    return save_data("hosts", fqdn, None)

# ======================================================================


@app.route("/groups", methods=['GET'])
@auth.login_required(role=['admin', 'user', 'viewer'])
def list_groups():
    return make_response(list(_groups.keys()))


@app.route("/groups/<name>", methods=['GET'])
@auth.login_required(role=['admin', 'user', 'viewer'])
def get_group(name):
    if name not in _groups:
        abort(404)
    return make_response(_groups.get(name))


@app.route("/groups", methods=['POST'])
@auth.login_required(role=['admin'])
def add_group():
    """Add a new group with name and with specified data (yaml format)"""
    name = request.form.get("name")
    if not name:
        abort(400)
    data = request.form.get("data")
    if not data:
        abort(400)
    return save_data("groups", name, yaml.safe_load(data))


@app.route("/groups/<name>", methods=['PUT'])
@auth.login_required(role=['admin'])
def update_group(name):
    data = _groups.get(name, {})
    if not data:
        abort(404)

    for k in request.form.keys():
        if k == "name":
            continue
        if k == "environment":
            data[k] = request.form.get(k)
        elif k == "classes":
            for v in request.form.getlist(k):
                if v.startswith("-"):
                    if v[:1] in data["classes"]:
                        del data["classes"][v[:1]]
                elif v not in data["classes"]:
                    data["classes"][v] = None
        elif k == "hosts":
            for v in request.form.getlist(k):
                if v.startswith("-"):
                    if v[:1] in data["hosts"]:
                        data["hosts"].remove(v[:1])
                elif v not in data["hosts"]:
                    data["hosts"].append(v)
        else:
            if isinstance(data["parameters"].get(k, None), list):
                for v in request.form.getlist(k):
                    if v.startswith("-"):
                        if v[:1] in data["parameters"][k]:
                            data["parameters"][k].remove(v[:1])
                    elif v not in data["parameters"][k]:
                        data["parameters"][k].append(v)
            else:
                v = request.form.get(k)
                if v.startswith("-"):
                    if k in data["parameters"] and v[:1] == data["parameters"][k]:
                        del data["parameters"][k]
                else:
                    data["parameters"][k] = v

    return save_data("groups", name, data)


@app.route("/groups/<name>", methods=['DELETE'])
@auth.login_required(role=['admin'])
def delete_group(name):
    if name not in _groups:
        abort(404)
    if name == "default"
        abort(403)
    return save_data("users", name, None)

# ======================================================================


@app.route("/users", methods=['GET'])
@auth.login_required(role=['admin'])
def list_users():
    return make_response(list(_users.keys()))


@app.route("/users/<username>", methods=['GET'])
@auth.login_required
def get_user(username):
    if username != auth.current_user() and "admin" not in get_user_roles(auth.current_user()):
        abort(403)
    if username not in _users:
        abort(404)
    return make_response(_users.get(username))


@app.route("/users", methods=['POST'])
@auth.login_required(role=['admin'])
def add_user():
    username = request.form.get("username")
    if not username:
        abort(400)
    if username in _users:
        abort(400)
    password = request.form.get("password")
    if not password:
        abort(400)
    password = generate_password_hash(password)
    roles = request.form.getlist("role")
    if not roles:
        roles = ["viewer"]
    user = {"password": password, "roles": roles}
    return save_data("users", username, user)


@app.route("/users/<username>", methods=['PUT'])
@auth.login_required(role=['admin'])
def update_user(username):
    user = _users.get(username, {})
    if not user:
        abort(404)

    password = request.form.get("password")
    if password:
        user['password'] = generate_password_hash(password)
    for v in request.form.getlist("roles"):
        if v.startswith("-"):
            if v[:1] in user["roles"]:
                user["roles"].remove(v[:1])
        elif v not in user["roles"]:
            user["roles"].append(v)
    return save_data('users', username, user)


@app.route("/users/<username>", methods=['DELETE'])
@auth.login_required(role=['admin'])
def delete_user(username):
    if username not in _users:
        abort(404)
    return save_data("users", username, None)

# ======================================================================


def represent_none(self, _):
    return self.represent_scalar('tag:yaml.org,2002:null', '')


# set yaml.dump to print empty value for None
yaml.add_representer(type(None), represent_none)

if __name__ == '__main__':
    app.run(debug=True)
