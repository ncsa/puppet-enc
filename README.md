## Puppet External Node Classifiers

This repository contains the code for a simple [puppet external node classifier](https://www.puppet.com/docs/puppet/8/nodes_external.html). This classifier uses a REST API to control the classifier, and can easily be added to the puppet server helm deployment. This will allow you to group nodes based on hostname patters, or explicitly on their hostnames. You can add users to managed the default patters, or manage hosts.

## Using puppet-enc

You can start the code on your local machine:

```bash
pip install -r requirements.txt
waitress-server enc.py
```

Pr you can use docker:

```bash
docker run --name enc --volume ${PWD}/enc:/app/data --ports 8080:8080 ncsa/puppet-enc
```

In both cases you can access the code at http://localhost:8080

Or you can use this with [puppet helm chart](https://github.com/puppetlabs/puppetserver-helm-chart) by adding the following snippet to your values.yaml file (to enable enc) and use the [deploy.yaml](deploy.yaml) file to deploy puppet-enc in the cluster.

```yaml
puppetserver:
  customentrypoints:
    enabled: true
    configmaps:
      90-custom.sh: |
        #!/bin/bash
        cat << EOF > /enc.sh
        #!/bin/bash
        curl -s -u puppet:viewer http://enc:8080/enc/hosts/\$1
        EOF
        chmod 755 /enc.sh
        /opt/puppetlabs/bin/puppet config set node_terminus "exec"
        /opt/puppetlabs/bin/puppet config set external_nodes "/enc.sh"
```

## Rest API

Following is a list of the REST endpoints. They will interact on individual hosts, group of hosts, users and miscalanous actions. All functions require a username and password. Users will have one of the following three roles, and certain actions require certain roles:

- **admin**: users in this group can do all actions on all objects
- **user**: can modify hosts
- **viewer**: can view hosts

### HOSTS

This will return output specified in the [complete example](https://www.puppet.com/docs/puppet/8/nodes_external.html#enc_output_format-section_oxs_qvm_thb) of the puppet documentation.

```yaml
foo.example.com
  classes:
  - profile::base
  environment: production
  parameters:
    project: moonshot
```

#### *GET /hosts* (**admin**, **user** or **viewer**)

Return a list of all hosts declared, this will not return hosts specified in the groups.

```bash
curl -s -u user:user http://localhost:5000/hosts
```

#### *GET /hosts/:fqdn* (**admin**, **user** or **viewer**)

Return the classifier for a single host, or matches a host the group definition. If none is found it will return the default group definition.

```bash
curl -s -u user:user http://localhost:5000/hosts/example.com
```

#### *POST /hosts* (**admin** or **user**)

Create a new host entry. This requires two fields, the fqdn and the host classifier as a yaml document

```bash
# if hostname.example.com does not exist this will use the default template
curl -s -o template.yaml http://localhost:5000/host/hostname.example.com
curl -s -u admin:admin http://localhost:5000/hosts -d fqdn=hostname.example.com --data-urlencode data@template.yaml
```

#### *PUT /hosts/:fqdn* (**admin**, **user** or **viewer**)

Updates a host definition. If the key of the property is either `environment` or  `classe`  it will update that field, otherwise it will asume it is a parameter. If the field is a list you can remove a single entry by prefixing that value with a `-`.

```bash
curl -X PUT -s -u user:user http://localhost:5000/hosts/example.com -d classes=special -d classes=-old
```

#### *DELETE /hosts/:fqdn* (**admin**)

Deletes a host definition. This will only delete a specific host, not remove the host from a group.

```bash
curl -X DELETE -s -u user:user http://localhost:5000/hosts/example.com
```

### GROUPS

Groups will allow you to use patterns and multiple hosts to define a classifier. For example this can be used to match all `web` servers, etc. The group definition is almost the same as a host classifier, with the extra field `hosts` which is used to match hosts. The special group definition `default` will be used for hosts that are not matched. All hosts mentioned in the default host are ignored.

```yaml
default:
  classes:
    profile::base:
  environment: production
  hosts: []
  parameters:
    project: undefined
```

#### *GET /groups* (**admin**, **user** or **viewer**)

Return a list of all groups declared.

```bash
curl -s -u user:user http://localhost:5000/groups
```

#### *GET /groups/:name* (**admin**, **user** or **viewer**)

Return the group definition for the specified name.

```bash
curl -s -u user:user http://localhost:5000/groups/default
```

#### *POST /groups* (**admin**)

Create a new group entry. This requires two fields, the name and the group definition as a yaml document.

```bash
curl -s -u admin:admin http://localhost:5000/groups -d name=webservers --data-urlencode data@group.yaml
```

#### *PUT /groups/:name* (**admin**)

Updates a group definition. If the key of the property is either `environment`, `classes`  or  `hosts`  it will update that field, otherwise it will asume it is a parameter. If the field is a list you can remove a single entry by prefixing that value with a `-`.

```bash
curl -X PUT -s -u admin:admin http://localhost:5000/groups/webservers -d classes=webservers
```

#### *DELETE /groups/:name* (**admin**)

Deletes a group definition. It is not possible to delete the `default` group.

```bash
curl -X DELETE -s -u admin:admin http://localhost:5000/groups/webservers
```

### USERS

Get user, if the user is not an admin they can only get their own info.
```yaml
user:
  password: pbkdf2:sha256:260000$EUBvsZZ0H6bTEDH9$f31057490735a2b6fcb4c8dab9e1c08ddb879a8347a3bd39c7ab0a6fdf94ec8a
  roles:
  - user
```

#### *GET /users* (**admin**)

Return a list of all users declared.

```bash
curl -s -u admin:admin http://localhost:5000/users
```

#### *GET /users/:username* (**admin**, **user** or **viewer**)

Return the user definition for the specified username. If the user is not an admin, only their own user information can be returned.

```bash
curl -s -u user:user http://localhost:5000/users/user
```

#### *POST /users* (**admin**)

Create a new user. This requires two fields, the username and the password. It is possible to specify the roles of the user as well, if no roles are specified the user is assigned the role viewer.

```bash
curl -s -u admin:admin http://localhost:5000/users -d username=bob -d password=foo -d roles=user
```

#### *PUT /users/:username* (**admin**)

Updates a user definition. In th case of roles you can remove a single entry by prefixing that value with a `-`. It is not possible to change the username

```bash
curl -X PUT -s -u admin:admin http://localhost:5000/users/bob -d roles=admin
```

#### *DELETE /users/:username* (**admin**)

Deletes a group definition. It is not possible to delete the `default` group.

```bash
curl -X DELETE -s -u admin:admin http://localhost:5000/users/bob
```

### MISC

#### *GET /healtz*

Used to check if the endpoint is alive. Will always return OK.
