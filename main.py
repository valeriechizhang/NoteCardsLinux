import random
import string
import httplib2
import json
import requests

from flask import Flask, render_template
from flask import request, redirect, jsonify, url_for, flash
from sqlalchemy import create_engine, asc
from sqlalchemy.orm import sessionmaker
from database_setup import Base, User, Notebook, Card
from flask import session as login_session

from oauth2client.client import flow_from_clientsecrets
from oauth2client.client import FlowExchangeError

from flask import make_response


app = Flask(__name__)

# Connect to Database and Create database session
engine = create_engine('postgresql://catalog:catalog@localhost/catalog')
Base.metadata.create_all(engine)

DBSession = sessionmaker(bind=engine)
session = DBSession()

# Load client_secrets.json file for Google login
CLIENT_ID = json.loads(
    open('/var/www/html/NoteCards/client_secrets.json', 'r').read())['web']['client_id']


# Page handler
@app.route('/')
@app.route('/notebook')
def showNotebooks():
    notebooks = session.query(Notebook).all()
    return render_template('allbooks.html', notebooks=notebooks)


@app.route('/notebook/new', methods=['GET', 'POST'])
def newNotebook():
    if 'user_id' not in login_session:
        return redirect(url_for('showNotebooks'))
    if request.method == 'POST':
        name = request.form['notebook_name']
        description = request.form['notebook_description']
        newbook = Notebook(name=name, description=description, user_id=login_session['user_id'])
        # validate if the name section is filled
        if name == '':
            error = 'The notebook\'s name should not be empty.'
            return render_template('newbook.html', error=error)
        session.add(newbook)
        session.commit()
        flash('New Notebook [%s] Successfully Created' % name)
        return redirect(url_for('showNotebooks'))
    else:
        return render_template('newbook.html')


@app.route('/notebook/<int:notebook_id>/edit', methods=['GET', 'POST'])
def editNotebook(notebook_id):
    if 'user_id' not in login_session:
        return redirect(url_for('showNotebooks'))
    notebook = session.query(Notebook).filter_by(id=notebook_id).one()
    # only allow the owner to edit the notebook
    if notebook.user_id != login_session['user_id']:
        return redirect(url_for('showNotebooks'))
    if request.method == 'POST':
        name = request.form['notebook_name']
        description = request.form['notebook_description']
        # validate if the name section is filled, and send out error message if it's empty
        if name == '':
            error = 'The notebook\'s name should not be empty.'
            return render_template('editbook.html', notebook=notebook, error=error)
        notebook.name = name
        notebook.description = description
        session.add(notebook)
        session.commit()
        flash("Notebook [%s] Successful Edited!" % notebook.name)
        return redirect(url_for('showNotebooks'))
    else:
        return render_template('editbook.html', notebook=notebook)


@app.route('/notebook/<int:notebook_id>/delete', methods=['GET', 'POST'])
def deleteNotebook(notebook_id):
    if 'user_id' not in login_session:
        return redirect(url_for('showNotebooks'))
    notebook = session.query(Notebook).filter_by(id=notebook_id).one()
    # only the owner can delete the notebook
    if notebook.user_id != login_session['user_id']:
        return redirect(url_for('showNotebooks'))
    if request.method == 'POST':
        # first delete all the cards in this book
        cards = session.query(Card).filter_by(notebook_id=notebook_id).all()
        for c in cards:
            session.delete(c)
            session.commit()
        # and then we delete the notebook
        session.delete(notebook)
        session.commit()
        flash("Notebook [%s] Successful Deleted!" % notebook.name)
        return redirect(url_for('showNotebooks'))
    else:
        return render_template('deletebook.html', notebook=notebook)


@app.route('/notebook/<int:notebook_id>')
@app.route('/notebook/<int:notebook_id>/card')
def showCards(notebook_id):
    cards = session.query(Card).filter_by(notebook_id=notebook_id).all()
    notebook = session.query(Notebook).filter_by(id=notebook_id).one()
    return render_template("cards.html", cards=cards, notebook=notebook)


@app.route('/notebook/<int:notebook_id>/card/new', methods=['GET', 'POST'])
def newCard(notebook_id):
    if 'email' not in login_session:
        return redirect(url_for('showCards', notebook_id=notebook_id))
    notebook = session.query(Notebook).filter_by(id=notebook_id).one()
    # only the notebook owner can create a new card inside
    if notebook.user_id != login_session['user_id']:
        return redirect(url_for('showCards', notebook_id=notebook_id))
    if request.method == 'POST':
        term = request.form['card_term']
        tag = request.form['card_tag']
        description = request.form['card_description']
        # validate the form input and send out error message
        if term == '':
            error = 'The card\'s term should not be empty.'
            return render_template('newcard.html', notebook_id=notebook_id, error=error)
        newcard = Card(term=term, tag=tag, description=description, notebook_id=notebook_id)
        session.add(newcard)
        session.commit()
        flash('New Card [%s] Successfully Created' % term)
        return redirect(url_for('showCards', notebook_id=notebook_id))
    else:
        return render_template('newcard.html', notebook_id=notebook_id)


@app.route('/notebook/<int:notebook_id>/card/<int:card_id>/edit', methods=['GET', 'POST'])
def editCard(notebook_id, card_id):
    if 'email' not in login_session:
        return redirect(url_for('showCards', notebook_id=notebook_id))
    notebook = session.query(Notebook).filter_by(id=notebook_id).one()
    # only the owner of the notebook can edit cards
    if notebook.user_id != login_session['user_id']:
        return redirect(url_for('showCards', notebook_id=notebook_id))
    card = session.query(Card).filter_by(id=card_id).one()
    if request.method == 'POST':
        term = request.form['card_term']
        tag = request.form['card_tag']
        description = request.form['card_description']
        # form validation and error message
        if term == '':
            error = 'The card\'s term should not be empty.'
            return render_template('editcard.html', card=card, notebook_id=notebook_id, error=error)
        card.term = term
        card.tag = tag
        card.description = description
        session.add(card)
        session.commit()
        flash("Card [%s] Successful Edited!" % card.term)
        return redirect(url_for('showCards', notebook_id=notebook_id))
    else:
        return render_template('editcard.html', card=card, notebook_id=notebook_id)


@app.route('/notebook/<int:notebook_id>/card/<int:card_id>/delete', methods=['GET', 'POST'])
def deleteCard(notebook_id, card_id):
    if 'email' not in login_session:
        return redirect(url_for('showCards', notebook_id=notebook_id))
    notebook = session.query(Notebook).filter_by(id=notebook_id).one()
    # only the notebooke owner can delete cards inside
    if notebook.user_id != login_session['user_id']:
        return redirect(url_for('showCards', notebook_id=notebook_id))
    card = session.query(Card).filter_by(id=card_id).one()
    if request.method == 'POST':
        session.delete(card)
        session.commit()
        flash("Card [%s] Successful Deleted!" % card.term)
        return redirect(url_for('showCards', notebook_id=notebook_id))
    else:
        return render_template('deletecard.html', card=card, notebook_id=notebook_id)


# JSON API endpoints
@app.route('/notebook/JSON')
def notebookJSON():
    notebooks = session.query(Notebook).all()
    return jsonify(notebooks=[n.serialize for n in notebooks])


@app.route('/notebook/<int:notebook_id>/card/JSON')
def notebookCardJSON(notebook_id):
    cards = session.query(Card).filter_by(notebook_id=notebook_id).all()
    return jsonify(cards=[c.serialize for c in cards])


@app.route('/notebook/card/<int:card_id>/JSON')
def cardJSON(card_id):
    card = session.query(Card).filter_by(id=card_id).one()
    return jsonify(card=card.serialize)


# User login helper functions
def createUser(login_session):
    newUser = User(name=login_session['username'], email=login_session['email'])
    session.add(newUser)
    session.commit()
    user = session.query(User).filter_by(email=login_session['email']).one()
    return user.id


def getUserInfo(user_id):
    user = session.query(User).filter_by(id=user_id).one()
    return user


def getUserID(email):
    try:
        user = session.query(User).filter_by(email=email).one()
        return user.id
    except:
        return None


# Login/logout pages
@app.route('/login')
def showLogin():
    state = ''.join(random.choice(string.ascii_uppercase + string.digits)
                    for x in xrange(32))
    login_session['state'] = state
    return render_template('login.html', STATE=state)


# Disconnect based on provider
@app.route('/disconnect')
def disconnect():
    if 'provider' in login_session:
        if login_session['provider'] == 'google':
            gdisconnect()
            del login_session['gplus_id']
            del login_session['access_token']
        if login_session['provider'] == 'facebook':
            fbdisconnect()
            del login_session['facebook_id']
        del login_session['username']
        del login_session['email']
        del login_session['user_id']
        del login_session['provider']
        flash("You have successfully been logged out.")
        return redirect(url_for('showNotebooks'))
    else:
        flash("You were not logged in")
        return redirect(url_for('showNotebooks'))


# Google login/disconnect methods
@app.route('/gconnect', methods=['POST'])
def gconnect():
    # Validate state token
    if request.args.get('state') != login_session['state']:
        response = make_response(json.dumps('Invalid state parameter.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    # Obtain authorization code
    code = request.data
    try:
        # Upgrade the authorization code into a credentials object
        oauth_flow = flow_from_clientsecrets('/var/www/html/NoteCards/client_secrets.json', scope='')
        oauth_flow.redirect_uri = 'postmessage'
        credentials = oauth_flow.step2_exchange(code)
    except FlowExchangeError:
        response = make_response(
            json.dumps('Failed to upgrade the authorization code.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Check that the access token is valid.
    access_token = credentials.access_token
    url = ('https://www.googleapis.com/oauth2/v1/tokeninfo?access_token=%s' % access_token)
    h = httplib2.Http()
    result = json.loads(h.request(url, 'GET')[1])
    # If there was an error in the access token info, abort.
    if result.get('error') is not None:
        response = make_response(json.dumps(result.get('error')), 500)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Verify that the access token is used for the intended user.
    gplus_id = credentials.id_token['sub']
    if result['user_id'] != gplus_id:
        response = make_response(
            json.dumps("Token's user ID doesn't match given user ID."), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Verify that the access token is valid for this app.
    if result['issued_to'] != CLIENT_ID:
        response = make_response(
            json.dumps("Token's client ID does not match app's."), 401)
        print "Token's client ID does not match app's."
        response.headers['Content-Type'] = 'application/json'
        return response

    stored_credentials = login_session.get('credentials')
    stored_gplus_id = login_session.get('gplus_id')
    if stored_credentials is not None and gplus_id == stored_gplus_id:
        response = make_response(json.dumps('Current user is already connected.'), 200)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Store the access token in the session for later use.
    login_session['access_token'] = credentials.access_token
    login_session['gplus_id'] = gplus_id

    # Get user info
    userinfo_url = "https://www.googleapis.com/oauth2/v1/userinfo"
    params = {'access_token': credentials.access_token, 'alt': 'json'}
    answer = requests.get(userinfo_url, params=params)

    data = answer.json()

    login_session['provider'] = 'google'
    login_session['username'] = data['name']
    login_session['email'] = data['email']

    user_id = getUserID(data['email'])
    if not user_id:
        user_id = createUser(login_session)
    login_session['user_id'] = user_id

    print login_session['user_id']
    print login_session['username']

    flash("you are now logged in as %s" % login_session['email'])
    return 'Login with %s' % login_session['email']


@app.route('/gdisconnect')
def gdisconnect():
    access_token = login_session['access_token']
    print 'In gdisconnect access token is %s', access_token
    print 'User name is: '
    print login_session['username']
    if access_token is None:
        print 'Access Token is None'
        response = make_response(json.dumps('Current user not connected.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    url = 'https://accounts.google.com/o/oauth2/revoke?token=%s' % login_session['access_token']
    h = httplib2.Http()
    result = h.request(url, 'GET')[0]
    if result['status'] == '200':
        response = make_response(
            json.dumps('Failed to revoke token for given user.'), 400)
        response.headers['Content-Type'] = 'application/json'
        return response


# Facebook login/logout methods
@app.route('/fbconnect', methods=['POST'])
def fbconnect():
    if request.args.get('state') != login_session['state']:
        response = make_response(json.dumps('Invalid state parameter.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    access_token = request.data
    print "access token received %s " % access_token

    app_id = json.loads(open('/var/www/html/NoteCards/fb_client_secrets.json', 'r').read())['web']['app_id']
    app_secret = json.loads(open('/var/www/html/NoteCards/fb_client_secrets.json', 'r').read())['web']['app_secret']
    #url = 'https://graph.facebook.com/oauth/access_token?grant_type=fb_exchange_token&client_id=%s&client_secret=%s&fb_exchange_token=%s' % (
    #    app_id, app_secret, access_token)
    url = ('https://graph.facebook.com/v2.8/oauth/access_token?'
           'grant_type=fb_exchange_token&client_id=%s&client_secret=%s'
           '&fb_exchange_token=%s') % (app_id, app_secret, access_token)
    h = httplib2.Http()
    result = h.request(url, 'GET')
    result = result[1]

    # Use token to get user info from API
    userinfo_url = "https://graph.facebook.com/v2.8/me"
    # strip expire tag from access token
    #token = result.split("&")[0]
    data = json.loads(result)
    token = 'access_token=' + data['access_token']

    url = 'https://graph.facebook.com/v2.8/me?%s&fields=name,id,email' % token
    h = httplib2.Http()
    result = h.request(url, 'GET')[1]
    print "url sent for API access:%s"% url
    print "API JSON result: %s" % result
    data = json.loads(result)
    login_session['provider'] = 'facebook'
    login_session['username'] = data["name"]
    login_session['email'] = data["email"]
    login_session['facebook_id'] = data["id"]

    # The token must be stored in the login_session in order to properly logout, let's strip out the information before the equals sign in our token
    stored_token = token.split("=")[1]
    login_session['access_token'] = stored_token

    # Get user picture
    url = 'https://graph.facebook.com/v2.8/me/picture?%s&redirect=0&height=200&width=200' % token
    h = httplib2.Http()
    result = h.request(url, 'GET')[1]
    data = json.loads(result)

    login_session['picture'] = data["data"]["url"]

    # see if user exists
    user_id = getUserID(login_session['email'])
    if not user_id:
        user_id = createUser(login_session)
    login_session['user_id'] = user_id

    flash("Now logged in as %s" % login_session['username'])
    return 'Login with %s' % login_session['email']


@app.route('/fbdisconnect')
def fbdisconnect():
    facebook_id = login_session['facebook_id']
    access_token = login_session['access_token']
    url = 'https://graph.facebook.com/%s/permissions?access_token=%s' % (facebook_id, access_token)
    h = httplib2.Http()
    result = h.request(url, 'DELETE')[1]
    return "You have been logged out."


if __name__ == '__main__':
    app.secret_key = 'super_secret_key'
    app.debug = True
    app.run()
    #app.run(host='0.0.0.0', port=5000)


