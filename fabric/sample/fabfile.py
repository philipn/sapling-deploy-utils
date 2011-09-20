from __future__ import with_statement
from fabric.api import *
from contextlib import contextmanager as _contextmanager


@_contextmanager
def virtualenv():
    with prefix(env.virtualenv_activate):
        yield


def production():
    # EDIT THIS:
    ################################
    env.wikiname = 'wikinamehere'
    env.hosts = ['example.org']
    env.user = 'deploy'
    env.git_root = '/srv/sites/%s/sapling/' % env.wikiname
    env.project_root = '/srv/sites/%s/sapling/' % env.wikiname
    env.virtualenv_activate = 'source /srv/sites/%s/env/bin/activate' % env.wikiname
    ################################


def init_solr_install():
    # create a new core
    sudo("cp -r /usr/share/solr/cores/denton /usr/share/solr/cores/%s" % env.wikiname)
    sudo("sed -i 's/denton/%s/g' /usr/share/solr/cores/%s/conf/solrconfig.xml" % (env.wikiname, env.wikiname))
    solr_xml = """<?xml version="1.0" encoding="UTF-8" ?>
<!--
 All (relative) paths are relative to the installation path

  persistent: Save changes made via the API to this file
  sharedLib: path to a lib directory that will be shared across all cores
-->
<solr persistent="false">

  <!--
  adminPath: RequestHandler path to manage cores.
    If 'null' (or absent), cores will not be manageable via request handler
  -->
  <cores adminPath="/admin/cores">
%s  </cores>
</solr>
"""
    cores = sudo("ls -1 /usr/share/solr/cores").split('\r')
    core_xml = ''
    for core in cores:
        core = core.strip()
        core_xml += ('     <core name="%s" instanceDir="cores/%s" />\n' % (core, core))
    local_xml = open('solr.xml', 'w')
    local_xml.write(solr_xml % core_xml)
    local_xml.close()

    put('solr.xml', 'solr.xml')
    sudo("mv /home/deploy/solr.xml /usr/share/solr/solr.xml")


def init_install():
    """
    This is very installation-dependent.
    Don't run this without looking at what it's doing.
    """
    import random
    import string

    rand_pass = ''.join([random.choice(string.letters + string.digits) for i in range(30)])
    sudo("cp -r /srv/sites/clean /srv/sites/%s" % env.wikiname, user="www-data")
    with cd(env.project_root):
        sudo("virtualenv ../env", user="www-data")

        sudo("""sudo -u postgres psql -c "create user %s with password '%s'" """ % (env.wikiname, rand_pass))
        sudo("sudo -u postgres createdb -E UTF8 -T template_postgis -O %s %s" % (env.wikiname, env.wikiname))

        sudo("sed -i 's/DBNAME_HERE/%s/g' sapling/localsettings.py" % env.wikiname, user="www-data")
        sudo("sed -i 's/USERNAME_HERE/%s/g' sapling/localsettings.py" % env.wikiname, user="www-data")
        sudo("sed -i 's/PASSWORD_HERE/%s/g' sapling/localsettings.py" % rand_pass, user="www-data")

        sudo("sed -i 's/SOLRNAME/%s/g' sapling/localsettings.py" % env.wikiname, user="www-data")

        sudo("sed -i 's/clean/%s/g' deploy/django.wsgi" % env.wikiname, user="www-data")

        with virtualenv():
            # site-specific packages that aren't in sapling proper
            # (e.g. django-extensions)
            sudo("pip install -r our_specific_requirements.txt")

    sudo("cp /etc/apache2/sites-available/clean /etc/apache2/sites-enabled/%s" % env.wikiname)
    sudo("sed -i 's/clean/%s/g' /etc/apache2/sites-enabled/%s" % (env.wikiname, env.wikiname))
    init_solr_install()

    update()
    restart_apache()


def git_update():
    with cd(env.git_root):
        sudo("git stash", user="www-data")
        sudo("git pull origin master", user="www-data")
        sudo("git stash pop", user="www-data")


def git_reset(hash):
    """
    Resets the repository to specified version.
    """
    with cd(env.git_root):
        # We do --merge rather than --hard because we have
        # locally-modified files that are tracked in the git index.
        # Example: themes/sapling/templates/site/base.html
        sudo("git reset --merge %s" % hash, user="www-data")


def restart_jetty():
    sudo("/etc/init.d/jetty stop")
    sudo("/etc/init.d/jetty start")


def restart_apache():
    sudo("/etc/init.d/apache2 restart")


def restart_cache():
    pass


def run_migrations():
    pass


def touch_wsgi():
    # Touching the deploy.wsgi file will cause apache's mod_wsgi to
    # reload all python modules having to restart apache.  This is b/c
    # we are running django.wsgi in daemon mode.
    with cd(env.project_root):
        sudo("touch deploy/django.wsgi")


def update(full=False):
    git_update()
    with cd(env.project_root):
        with virtualenv():
            run_migrations()
            sudo("pip install -r install_config/requirements.txt")
            sudo("python sapling/manage.py collectstatic")
            sudo("python sapling/manage.py syncdb")
            sudo("cp install_config/daisydiff.war /usr/share/jetty/webapps")
    touch_wsgi()
    restart_cache()
    restart_jetty()


def rollback(git_hash=None):
    """
    Roll back to the version of the site specified by the git_hash.
    If git_hash isn't provided then we reset to the previous commit.

    Usage:
        fab <site> rollback:hash=etcetc123
    """
    if git_hash is None:
        git_hash = "HEAD~1"

    with cd(env.project_root):
        with virtualenv():
            # TODO: We'll need to specify something here.
            # reverse_migrations()
            pass

    git_reset(git_hash)

    with cd(env.project_root):
        with virtualenv():
            sudo("pip install -r install_config/requirements.txt")
            sudo("python sapling/manage.py collectstatic")
            sudo("python sapling/manage.py syncdb")
            sudo("cp install_config/daisydiff.war /usr/share/jetty/webapps")
    touch_wsgi()
    restart_cache()
    restart_jetty()


def deploy():
    update()
