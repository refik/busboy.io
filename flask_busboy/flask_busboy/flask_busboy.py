import os
import re
import sqlite3
from flask import Flask, request, session, g, redirect, url_for, abort, \
     render_template, flash
import requests
import putiopy
import time

app = Flask(__name__) # create the application instance :)
app.config.from_object(__name__) # load config from this file , flask_busboy.py

# Load default config and override config from an environment variable
app.config.update(dict(
    DATABASE=os.path.join(app.root_path, 'flask_busboy.db'),
    SECRET_KEY='development key',
    USERNAME='admin',
    PASSWORD='default'
))

app.config.from_envvar('BUSBOY_SETTINGS', silent=True)

def connect_db():
    """Connects to the specific database."""
    rv = sqlite3.connect(app.config['DATABASE'])
    rv.row_factory = sqlite3.Row
    return rv

def get_db():
    """Opens a new database connection if there is none yet for the
    current application context.
    """
    if not hasattr(g, 'sqlite_db'):
        g.sqlite_db = connect_db()
    return g.sqlite_db

@app.teardown_appcontext
def close_db(error):
    """Closes the database again at the end of the request."""
    if hasattr(g, 'sqlite_db'):
        g.sqlite_db.close()

def search_title_omdb(title):
    response = requests.get("https://www.omdbapi.com", params={
        'apikey': '31eec4b0',
        's': title
    })

    title_list = response.json()['Search']

    # Filter movie and series
    title_list = [title for title in title_list if title['Type'] in ['movie', 'series']]

    return title_list[:5]

def get_title_omdb(imdb_id):
    response = requests.get("https://www.omdbapi.com", params={
        'apikey': '31eec4b0',
        'i': imdb_id
    })

    return response.json()

@app.route('/title/<imdb_id>')
def show_title(imdb_id):
    if not session.get('logged_in'):
        return redirect(url_for('register'))

    title = get_title_omdb(imdb_id)
    return render_template('title.html', title=title)

@app.route('/add/<imdb_id>')
def add_title(imdb_id):
    title = get_title_omdb(imdb_id)

    db = get_db()
    db.execute('insert into add_request (imdb_id, seasons, username) values (?, ?, ?)',
               [imdb_id, request.args.get('seasons'), session['username']])
    db.commit()

    if title['Type'] == 'series':
        seasons = request.args.get('seasons')
        seasons_head = seasons.split(',')[:3]
        get_seasons(imdb_id, seasons_head)
    else:
        seasons_head = None

    torrents = get_torrent(imdb_id)
    folders = create_title_folder(session['username'], title)

    download_folder = folders['download_folder']
    title_folder = folders['title_folder']
    relevant_torrent = get_relevant_torrent(torrents, seasons_head)

    for torrent in relevant_torrent:
        download_folder.client.Transfer.add_url(
            torrent,
            parent_id=download_folder.id,
            callback_url='http://' + request.environ['HTTP_HOST'] + '/transfer-complete/' + session['username'] + '/' + str(title_folder.id) + '/' + imdb_id)

    return render_template('complete.html')

@app.route('/transfer-complete/<username>/<int:title_file_id>/<imdb_id>', methods = ['POST'])
def transfer_complete(username, title_file_id, imdb_id):
    file_to_episode(username, int(request.form['file_id']), imdb_id, title_file_id)
    return('Thank you sir')

def get_relevant_torrent(torrents, seasons_head):
    if seasons_head == None:
        return torrents[0]

    torrent_dict = {}

    season_filter = ['S' + format(int(s), '02') for s in seasons_head]

    for torrent in torrents[::-1]:
        match = re.search('S[0-9]{2}E[0-9]{2}', torrent['filename'])
        if not match:
            match = re.search('(?<=\.)S[0-9]{2}', torrent['filename'])

        if match:
            torrent_dict[match.group(0)] = torrent['download']

    full_season = [k for k in torrent_dict.keys() if len(k) == 3]
    episodes = [k for k in torrent_dict.keys() if len(k) == 6]
    ok_episodes = [e for e in episodes if e[:3] not in full_season]
    ok_keys = ok_episodes + full_season
    ok_keys = [k for k in ok_keys if k[:3] in season_filter]
    download_list = [magnet for key, magnet in torrent_dict.items() if key in ok_keys]
    return download_list

@app.route('/')
def search():
    return render_template('search.html')


@app.route('/search')
def search_title():
    search_query = request.args.get('q').rstrip()
    title_list = search_title_omdb(search_query)
    return render_template('list_titles.html',
                           search_query=search_query,
                           title_list=title_list)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form['username'] != app.config['USERNAME']:
            error = 'Invalid username'
        elif request.form['password'] != app.config['PASSWORD']:
            error = 'Invalid password'
        else:
            session['logged_in'] = True
            flash('You were logged in')
            return redirect(url_for('show_entries'))

        db = get_db()
        cur = db.execute('select password from user where username=?',
                   [request.form['username']])
        pass_proxy = cur.fetchone()

        if pass_proxy:
            password = pass_proxy[0]
            if password == request.form['password']:
                session['logged_in'] = True
                session['username'] = request.form['username']
                return redirect('/')
        else:
            return redirect(url_for('login'))

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('username', None)
    session.pop('logged_in', None)
    return redirect("/")

@app.route('/putio-callback')
def putio_callback():
    code = request.args.get('code')
    username = session['username']
    response = requests.get("https://api.put.io/v2/oauth2/access_token", params={
        'client_id': 3129,
        'client_secret': 'AQCGSDFTEBNUOIA66AF5',
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': 'https://busboy.io/putio-callback'
    })
    access_token = response.json()['access_token']
    db = get_db()
    db.execute('update user set auth_token=? where username=?',
               [access_token, username])
    db.commit()
    return redirect("/")

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == "POST":
        db = get_db()
        db.execute('insert into user (username, password) values (?, ?)',
                   [request.form['username'], request.form['password']])
        db.commit()
        session['logged_in'] = True
        session['username'] = request.form['username']
        callback = 'http://' + request.environ['HTTP_HOST'] + '/putio-callback'
        return redirect("https://api.put.io/v2/oauth2/authenticate?client_id=3129&response_type=code&redirect_uri=" + callback)
    return render_template('register.html')

def init_db():
    db = get_db()
    with app.open_resource('schema.sql', mode='r') as f:
        db.cursor().executescript(f.read())
    db.commit()

@app.cli.command('initdb')
def initdb_command():
    """Initializes the database."""
    init_db()
    print('Initialized the database.')


def get_torrent(imdb_id):
    token = requests.get('https://torrentapi.org/pubapi_v2.php?get_token=get_token').json()['token']
    time.sleep(1)
    response = requests.get('https://torrentapi.org/pubapi_v2.php', params={
        'token': token,
        'mode': 'search',
        'search_imdb': imdb_id,
        'limit': '100'
    })

    torrents = response.json()['torrent_results']
    return torrents[::-1]

def get_seasons(imdb_id, seasons):
    db = get_db()

    for season in seasons:
        season_padded = format(int(season), '02')

        response = requests.get("https://www.omdbapi.com", params={
            'apikey': '31eec4b0',
            'i': imdb_id,
            'Season': season
        }).json()

        time.sleep(0.5)

        if 'Episodes' in response.keys():
            for episode in response['Episodes']:
                episode_padded = format(int(episode['Episode']), '02')
                episode_denormalized = 'S' + season_padded + 'E' + episode_padded
                db.execute('insert into episode (title_imdb_id, episode_title, episode_denormalized) values (?, ?, ?)',
                           [imdb_id, episode['Title'], episode_denormalized])

    db.commit()


def find_or_create_file(files, name, parent=None):
    if len(files) == 0:
        parent_id = parent.id
        return parent.client.File.create_folder(name, parent_id=parent_id)
    else:
        parent_id = files[0].parent_id

    for candidate in files:
        if candidate.name == name:
            return candidate
    else:
        return files[0].client.File.create_folder(name, parent_id=parent_id)


def create_title_folder(username, title):
    db = get_db()
    auth_token = db.execute('select auth_token from user where username=?', [username]).fetchone()[0]
    client = putiopy.Client(auth_token)
    files = client.File.list()
    busboy_folder = find_or_create_file(files, 'busboy')

    if not busboy_folder:
        busboy_folder = client.File.create_folder('busboy')

    busboy_files = client.File.list(parent_id=busboy_folder.id)

    movie_folder = find_or_create_file(busboy_files, 'Movie', parent=busboy_folder)
    series_folder = find_or_create_file(busboy_files, 'Series', parent=busboy_folder)
    download_folder = find_or_create_file(busboy_files, 'Files to Organize', parent=busboy_folder)
    series = client.File.list(parent_id=series_folder.id)

    if (title['Type'] == 'series'):
        title_folder = find_or_create_file(series, title['Title'], parent=series_folder)
    else:
        title_folder = movie_folder

    return {'title_folder': title_folder, 'download_folder': download_folder}

def file_to_episode(username, file_id, imdb_id, title_file_id):
    db = get_db()
    auth_token = db.execute('select auth_token from user where username=?', [username]).fetchone()[0]
    client = putiopy.Client(auth_token)

    title_file = client.File.get(title_file_id)
    file = client.File.get(file_id)
    title = get_title_omdb(imdb_id)

    files = client.File.list(parent_id=file_id)

    if title['Type'] != 'series':
        videos = [file for file in files if file.file_type == 'VIDEO']
        videos.sort(key=lambda x: x.size, reverse=True)
        video = videos[0]
        video.rename(title['Title'])
        video.move(title_file_id)
        file.delete()
        return


    season = str(int(re.search('(?<=S)[0-9]{2}', file.name).group(0)))
    season_file = find_or_create_file(client.File.list(parent_id=title_file_id), "Season " + season, title_file)

    videos = [file for file in files if file.file_type == 'VIDEO' and re.search('S[0-9]{2}E[0-9]{2}', file.name.upper())]
    ep_key = [re.search('S[0-9]{2}E[0-9]{2}', video.name.upper()).group(0) for video in videos]

    cursor = db.execute('select episode_denormalized, episode_title from episode where title_imdb_id=?', [imdb_id]).fetchall()
    episode_dict = dict([(r[0], r[0][4:6] + ' - ' + r[1]) for r in cursor])

    torrent_episodes = ep_key.keys()
    db_episodes = episode_dict.keys()

    for torrent_episode in torrent_episodes:
        if torrent_episode not in db_episodes:
            episode_dict[torrent_episode] = torrent_episode[1:3]

    ep_good_names = [episode_dict[key] for key in ep_key]

    for i in range(len(videos)):
        video = videos[i].rename(ep_good_names[i])
        videos[i].move(season_file.id)

    file.delete()

