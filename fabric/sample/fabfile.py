from fabric.api import *


def production():
    env.hosts = ['example.org']
    env.user = 'deploy'
    env.git_root = '/srv/sites/example/sapling/'
    env.project_root = '/srv/sites/example/sapling/'
    env.python_path = '/srv/sites/example/env/bin/python'


def git_update():
    with cd(env.git_root):
        sudo("git pull origin master", user="www-data")


def restart_services():
    sudo("/etc/init.d/apache2 restart")
    sudo("/etc/init.d/jetty stop")
    sudo("/etc/init.d/jetty start")


def restart_cache():
    pass


def run_migrations():
    pass


def update(full=False):
    git_update()
    with cd(env.project_root):
        run_migrations()
        sudo("pip install -r install_config/requirements.txt")
        sudo("%s sapling/manage.py collectstatic --noinput" % env.python_path)
        sudo("%s sapling/manage.py syncdb" % env.python_path)
        sudo("cp install_config/daisydiff.war /usr/share/jetty/webapps")
    restart_cache()
    restart_services()


def deploy():
    update()
