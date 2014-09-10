import os
import string
import random

from fabric.api import *
from fabric.contrib.files import append
from fabric.colors import green


# public functions
__all__ = [
    'install',
    'update'
]


def generate_random_password():
    """ generates random password """
    return ''.join(random.choice(string.ascii_lowercase + string.digits) for _ in range(12))


def cmd(*args, **kwargs):
    """ use sudo if current user is not root """
    if env['user'] == 'root':
        return run(*args, **kwargs)
    else:
        return sudo(*args, **kwargs)


def install():
    initialize()
    initialize_server()
    initialize_db()
    initialize_ssl()
    install_dependencies()
    create_db()
    create_python_virtualenv()
    install_python_requirements()
    create_project()
    edit_settings()
    install_redis()
    sync_data()
    create_admin()
    configure_nginx()
    install_uwsgi()
    configure_supervisor()
    install_postfix()
    restart_services()
    completed_message()


def update(**kwargs):
    global root_dir
    global fabfile_dir
    global project_name
    root_dir = kwargs.get('root_dir', '/var/www')  # defaults to /var/www/
    project_name = kwargs.get('project_name')
    # if no parameter supplied
    if project_name is None:
        # ask
        initialize_dirs()
    install_python_requirements()
    sync_data(update=True)
    restart_services()
    print(green("UPDATE COMPLETED !"))


# ------ internal functions ------ #


def initialize():
    if 'root_dir' not in globals():
        initialize_dirs()


def initialize_dirs():
    global root_dir
    global project_name
    global nodeshot_dir
    global fabfile_dir
    global tmp_dir
    global use_sudo
    root_dir = prompt('Set install directory (including trailing slash): ', default='/var/www')
    project_name = prompt('Set project name: ', default='myproject')
    nodeshot_dir = '%s/nodeshot' % root_dir
    fabfile_dir = os.path.dirname(__file__)
    tmp_dir = '~/nodeshot_install'
    with hide('everything'):
        run('mkdir -p %s' % tmp_dir)
    with cd(tmp_dir), hide('everything'):
        tmp_dir = run('pwd')
    with quiet():
        use_sudo = env['user'] != 'root'


def initialize_server():
    if 'server_name' not in globals():
        global server_name
        server_name = prompt('Server name: ', default=env['host'])


def initialize_db():
    db_params = ('db_user','db_pass')
    for db_param in db_params:
        if db_param not in globals():
            global db_user
            global db_pass
            db_user = prompt('Set database user: ', default='nodeshot')
            db_pass = prompt('Set database user password: ', default=generate_random_password())


def initialize_ssl():
    with quiet():
        openssl_installed = run('which openssl').succeeded

    if not openssl_installed:
        print(green("openssl command not found, installing it..."))
        with hide('everything'):
            cmd('apt-get install -y openssl')

    print(green("****************************************"))
    print(green("Please insert SSL certificate details..."))
    print(green("****************************************"))

    with cd(tmp_dir):
        run('openssl req -new -x509 -nodes -days 365 -out server.crt -keyout server.key')


def install_dependencies():
    initialize()
    print(green("Installing required packages. This will take a bit of time to download..."))
    with hide('stdout', 'stderr'):
        cmd('apt-get update -y')
        path = '{path}/dependencies.txt'.format(path=fabfile_dir)
        # read dependencies, put them on one line
        dependencies = ' '.join([line.replace('\n', '') for line in open(path).readlines()])
        # install
        cmd('apt-get install -y %s' % dependencies)
        # install Postgis 2
        with quiet():
            postgis_installed = run('dpkg --get-selections | grep "postgis\s"').succeeded
        if not postgis_installed:
            with cd(tmp_dir):
                cmd('wget http://download.osgeo.org/postgis/source/postgis-2.1.3.tar.gz')
                cmd('tar xfvz postgis-2.1.3.tar.gz')
            with cd('%s/postgis-2.1.3' % tmp_dir):
                cmd('./configure')
                cmd('make')
            # on debian 7 the procedure aborts if we don't do this
            with quiet():
                contrib_dir_exists = cmd('test -f /usr/share/postgresql/9.1/contrib').succeeded
                if not contrib_dir_exists:
                    cmd("mkdir -p '/usr/share/postgresql/9.1/contrib/postgis-2.1'")
            with cd('%s/postgis-2.1.3' % tmp_dir):
                cmd('checkinstall -y')


def create_db():
    initialize_db()
    print(green("Configuring DB..."))
    with hide('everything'):
        db_sql = open('%s/db.sql' % fabfile_dir).read()
        db_sql = db_sql.replace('<user>', db_user)
        db_sql = db_sql.replace('<password>', db_pass)
        append(filename='/tmp/db.sql', text=db_sql, use_sudo=use_sudo)
        cmd('chmod 777 /tmp/db.sql')
        cmd('su - postgres -c "psql -f /tmp/db.sql"')
        cmd('rm /tmp/db.sql')


def create_python_virtualenv():
    initialize()
    print(green("Creating virtual env..."))
    with hide('everything'):
        cmd('pip install virtualenvwrapper')
        cmd("echo 'source /usr/local/bin/virtualenvwrapper.sh' >> ~/.bash_profile")
        cmd("echo 'source /usr/local/bin/virtualenvwrapper.sh' >> /root/.bashrc")
        cmd("chown -R {user}:{user} ~/.virtualenvs".format(user=env['user']))
        run('mkvirtualenv nodeshot')


def install_python_requirements():
    initialize()
    print(green("Installing requirements. This will take a while, sit back and relax..."))
    with hide('stdout', 'stderr'):
        run('workon nodeshot && pip install -U distribute')
        run('workon nodeshot && pip install -U https://github.com/ninuxorg/nodeshot/tarball/master')


def create_project():
    initialize()
    print(green("Creating project..."))
    with hide('everything'):
        cmd('mkdir -p %s' % nodeshot_dir)
    with cd(root_dir), hide('everything'):
        cmd('workon nodeshot && nodeshot startproject %s nodeshot' % project_name)
    print(green("Setting permissions..."))
    with cd(nodeshot_dir), hide('everything'):
        cmd('chown -R %s:www-data .' % env['user'])
        cmd('adduser www-data %s' % env['user'])
        cmd('chmod 775 . log %s' % project_name)
        cmd('chmod 750 manage.py ./%s/*.py' % project_name)


def edit_settings():
    initialize()
    initialize_db()
    initialize_server()
    print(green("Configuring nodeshot..."))
    with cd('%s/%s' % (nodeshot_dir, project_name)), hide('everything'):
        cmd('sed -i \'s#<user>#%s#g\' settings.py' % db_user)
        cmd('sed -i \'s#<password>#%s#g\' settings.py' % db_pass)
        cmd('sed -i \'s#<domain>#%s#g\' settings.py' % server_name)
        cmd('sed -i \'s#DEBUG = True#DEBUG = False#g\' settings.py')


def install_redis():
    initialize()
    print(green("Installing redis..."))
    with hide('everything'):
        cmd('apt-get -y --force-yes install redis-server')
        run('workon nodeshot && pip install -U celery[redis]')
        cmd('echo 1 > /proc/sys/vm/overcommit_memory')
        cmd('service redis-server restart')


def sync_data(update=None):
    initialize()
    print(green("Initializing nodeshot..."))
    sync_command = './manage.py syncdb --noinput && ./manage.py migrate && ./manage.py collectstatic --noinput'
    if update is not None:
        sync_command = './manage.py syncdb --no-initial-data && ./manage.py migrate --no-initial-data && ./manage.py collectstatic --noinput'
    with cd(nodeshot_dir), hide('everything'):
        run('workon nodeshot && %s' % sync_command)


def create_admin():
    initialize()
    print(green("Creating nodeshot admin account..."))
    create_admin_oneliner = """echo "from nodeshot.community.profiles.models import Profile;\
                            Profile.objects.create_superuser('admin', '', 'admin')" | ./manage.py shell"""
    with cd(nodeshot_dir), hide('everything'):
        cmd('workon nodeshot && %s' % create_admin_oneliner)


def configure_nginx():
    initialize()
    initialize_server()
    print(green("Configuring nginx..."))
    nginx_ssl_dir = '/etc/nginx/ssl'
    with hide('everything'):
        cmd('mkdir -p %s' % nginx_ssl_dir)
    with cd(nginx_ssl_dir), hide('everything'):
        cmd('cp ~/nodeshot_install/server.crt .')
        cmd('cp ~/nodeshot_install/server.key .')
        cmd('cp /etc/nginx/uwsgi_params /etc/nginx/sites-available/')
        cmd('mkdir -p %s/public_html' % nodeshot_dir)

    with hide('everything'):
        nginx_conf = open('%s/nginx.conf' % fabfile_dir).read()
        nginx_conf = nginx_conf.replace('<server_name>', server_name)
        nginx_conf = nginx_conf.replace('<nodeshot_dir>', nodeshot_dir)
        nginx_conf = nginx_conf.replace('<project_name>', project_name)
        append(filename='/etc/nginx/sites-available/%s' % server_name,
               text=nginx_conf,
               use_sudo=use_sudo)

    with cd('/etc/nginx/sites-available'), hide('everything'):
        cmd('ln -s /etc/nginx/sites-available/{0} /etc/nginx/sites-enabled/{0}'.format(server_name))
        cmd('service nginx configtest')


def install_uwsgi():
    initialize()
    print(green("Installing uwsgi..."))
    with hide('everything'):
        cmd('pip install uwsgi')
        uwsgi_ini = open('%s/uwsgi.ini' % fabfile_dir).read()
        uwsgi_ini = uwsgi_ini.replace('<nodeshot_dir>', nodeshot_dir)
        uwsgi_ini = uwsgi_ini.replace('<project_name>', project_name)
        python_home = '%s/nodeshot' % run('echo $WORKON_HOME')
        uwsgi_ini = uwsgi_ini.replace('<python_home>', python_home)
        append(filename='%s/uwsgi.ini' % nodeshot_dir,
               text=uwsgi_ini,
               use_sudo=use_sudo)


def configure_supervisor():
    initialize()
    print(green("Installing & configuring supervisor..."))
    with hide('everything'):
        uwsgi_conf = open('%s/uwsgi.conf' % fabfile_dir).read()
        uwsgi_conf = uwsgi_conf.replace('<nodeshot_dir>', nodeshot_dir)
        append(filename='/etc/supervisor/conf.d/uwsgi.conf', text=uwsgi_conf, use_sudo=use_sudo)

        python_home = '%s/nodeshot' % run('echo $WORKON_HOME')

        celery_conf = open('%s/celery.conf' % fabfile_dir).read()
        celery_conf = celery_conf.replace('<nodeshot_dir>', nodeshot_dir)
        celery_conf = celery_conf.replace('<project_name>', project_name)
        celery_conf = celery_conf.replace('<python_home>', python_home)
        append(filename='/etc/supervisor/conf.d/celery.conf', text=celery_conf, use_sudo=use_sudo)

        celerybeat_conf = open('%s/celery-beat.conf' % fabfile_dir).read()
        celerybeat_conf = celerybeat_conf.replace('<nodeshot_dir>', nodeshot_dir)
        celerybeat_conf = celerybeat_conf.replace('<project_name>', project_name)
        celerybeat_conf = celerybeat_conf.replace('<python_home>', python_home)
        append(filename='/etc/supervisor/conf.d/celery-beat.conf', text=celerybeat_conf, use_sudo=use_sudo)

        cmd('supervisorctl update')

        # check all processes are running correctly
        # TODO


def install_postfix():
    initialize()
    initialize_server()
    print(green("Installing & configuring postfix..."))
    with hide('everything'):
        cmd('export DEBIAN_FRONTEND=noninteractive && apt-get -y install postfix')
        postfix_conf = open('%s/postfix.cf' % fabfile_dir).read()
        postfix_conf = postfix_conf.replace('<server_name>', server_name)
        append(filename='/etc/postfix/main.cf', text=postfix_conf, use_sudo=use_sudo)


def restart_services():
    initialize()
    print(green("Starting nodeshot..."))
    cmd('service nginx restart && supervisorctl restart all')
    print(green("Nodeshot server started"))
    print(green("Cleaning installation directory..."))
    cmd('rm -rf ~/nodeshot_install')


def completed_message():
    initialize_server()
    print(green("\nINSTALLATION COMPLETED !\n"))
    print(green("#############################################################"))
    print(green("                           WARNING:                         "))
    print(green(" Superuser is currently set as 'admin' with password 'admin'"))
    print(green(" Log in on https://%s/admin and change it " % server_name))
    print(green("#############################################################"))
