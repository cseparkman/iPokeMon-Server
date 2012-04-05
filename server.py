from bottle import Bottle, run, request, response
import redis
from hashlib import md5
import time

server = Bottle()
RADIS_HOST = '127.0.0.1'
REDIS_PORT = 6379
REDIS_DB   = 8

# Request Header
class Header(object):
    def __init__(self, headers):
        self.headers = headers

    # Make sure the request is sent via App
    def auth(self):
        if self.headers.get('key') == '123456':
            return True
        else:
            return False

    # Get <provider>
    def get_provider(self):
        return self.headers.get('provider')

    # Get <identity>
    def get_identity(self):
        return self.headers.get('identity')

    # Get <region>
    def get_region(self):
        return self.headers.get('region')


# <xxx>  : Basic
# <!xxx!>: Encrypted

# OpenID for users
# openid:<userid> => A set of <provider> that the user has activated
# 
# <provider>:<!identity!> => <userID>
class OpenID(object):
    def __init__(self, p_provider, p_identity):
        self.redis    = redis.Redis(RADIS_HOST, REDIS_PORT, REDIS_DB)
        self.provider = p_provider
        self.identity = p_identity

    # The user has no OpenID added before, so add new, and return the new <userid>
    def add(self):
        # Get the new user's ID
        userid = self.redis.incr("global:nextUserid")
        # If add new openID successed(it's value is <userid>),
        # then add new user
        if self.redis.setnx("%s:%s" % (self.provider, md5(self.identity).hexdigest()), userid):
            self.redis.sadd("openid:%s" % userid, self.provider)
            self.redis.setnx('u:%s:p'   % userid, 0) # UsersPokemonsID
            if User(userid).add(
                    "Trainer%s" % userid, # Name
                    time.time(),          # Time started
                    1000,                 # Money
                    "0,0,0",              # Badges
                    "",                   # Six Pokemons
                    "",                   # Pokedex
                    0,                    # Number of Pokemons
                    "0_0_0_0_0_0_0_0_0"   # Bag
                    ):
                return userid
        else:
            return 0

    # The user has one or several OpenIDs, add one more OpenID for user
    def add_to_user(self):
        if self.redis.setnx("%s:%s" % (self.provider, md5(self.identity).hexdigest()), self.userid):
            return True
        else:
            return False

    # Remove an OpenID from the user
    def rm_from_user(self):
        if self.redis.delete("%s:%s" % (self.provider, md5(self.identity).hexdigest())):
            return True
        else:
            return False

    # After authenticated, return the authorized user's <userid>
    def authorized_user(self):
        return self.redis.get("%s:%s" % (self.provider, md5(self.identity).hexdigest()))

    # Authenticate the user by <provider> & <identity>
    def authenticate(self):
        return self.redis.get("%s:%s" % (self.provider, md5(self.identity).hexdigest()))
        #if self.redis.sismember("%s:%s" % (self.provider, md5(self.identity).hexdigest()), userid):
        #    return True
        #else:
        #    return False

# User
# users: a set of <userid>
#
# u: User
# u:<userID> => {
#       "id"          : <userid>,       # Number
#       "name"        : <username>,     # String
#       "timeStarted" : <timeStarted>,  # Date
#       "money"       : <money>,        # Number
#       "badges"      : <badges>,       # 
#       "sixPokemons" : <sixPokemons>,  # String e.g. "1,2,3,4,5,6"
#       "pokedex"     : <pokedex>,      # String e.g. "101111100..."
#       "pokemons"    : <pokemons>,     # Number e.g. 6
#       "bag"         : <bag>           # String
#       }
#       
#  AS:
#       <bag>: <bagItems>_<bagMedicineStatus>_<bagMedicineHP>_<bagMedicinePP>
#           _<bagPokeballs>_<bagTMsHMs>_<bagBerries>_<bagBattleItems>_<bagKeyItems>
#     & <bagItems>, <...>: "1,2,3,..."
#  SO:
#       <bag>: "1,2,3_1,2,3_..._1,2,3"                                              
class User(object):
    def __init__(self, p_user_id):
        self.redis  = redis.Redis(RADIS_HOST, REDIS_PORT, REDIS_DB)
        self.userid = p_user_id

    # Get all data for a user with <userid>
    def get(self):
        #return self.redis.hget("u:%s" % userid, "name")
        return self.redis.hgetall("u:%s" % self.userid)

    def check_name_uniqueness(self, p_username):
        return self.redis.sismember("usernames",p_username)

    # Update data for user
    def update(self, p_userdata):
        #if self.redis.sismember("u:%s" % self.userid):
        if self.redis.sismember("users", self.userid):
            self.redis.hmset("u:%s" % self.userid, p_userdata)
            return True
        else:
            return False

    
    # Add new user
    def add(self, p_username, p_timeStarted, p_money, p_badges,
            p_sixPokemons, p_pokedex, p_pokemons, p_bag):
        # If add user successed, i.e. <userid> does not exist in <users> set
        if self.redis.sadd("users", self.userid):
            self.redis.sadd("usernames", p_username)
            #self.redis.hset("u:%s" % self.userid, "name",    p_username)
            #self.redis.hset("u:%s" % self.userid, "pokedex", p_pokedex)
            self.redis.hmset("u:%s" % self.userid, {
                "id":          self.userid,
                "name":        p_username,
                "timeStarted": p_timeStarted,
                "money":       p_money,
                "badges":      p_badges,
                "sixPokemons": p_sixPokemons,
                "pokedex":     p_pokedex,
                "pokemons":    p_pokemons,
                "bag":         p_bag
                })
            return True
        else:
            return False


# Tamed Pokemon
# pokedex:<userid> => a set of <pokemon_uid>,
#                     which belong to the user with <userid>.
#
# pm: PokeMon
# pm:<uid> => {
#       "uid":         <uid>,         # Number. Pokemon's Unique ID
#       "sid":         <sid>,         # Number. Pokemon's Pokedex Number ID
#       "box":         <box>,         # Number.
#       "status":      <status>,      # Number.
#       "gender":      <gender>,      # Number.
#       "happiness":   <happiness>,   # Number.
#       "level":       <level>,       # Number.
#       "fourMoves":   <fourMoves>,   # String. e.g. "1,2,3,4"
#       "maxStats":    <maxStats>,    # String. e.g. "30,30,30,30,30,30"
#       "currHP":      <currHP>,      # Number.
#       "currEXP":     <currEXP>,     # Number.
#       "toNextLevel": <toNextLevel>, # Number.
#       "memo":        <memo>         # String. e.g. "It is caught at ZJUT."
#       }
class Pokemon(object):
    def __init__(self, p_userid):
        self.redis  = redis.Redis(RADIS_HOST, REDIS_PORT, REDIS_DB)
        self.userid = p_userid

    # Get a dict data for a Pokemon
    def get_one(self, p_pokemon_uid):
        return self.redis.hgetall("pm:%s:%s" % (self.userid, p_pokemon_uid))

    # Get add data for a user's six Pokemon
    def get_six(self):
        six_pokemons = self.redis.hget("u:%s" % self.userid, "sixPokemons")
        if not six_pokemons:
            return
        import ast
        six_pokemons = ast.literal_eval(six_pokemons)
        if type(six_pokemons) is int:
            return six_pokemons
        pokemons = []
        for pokemon_uid in six_pokemons:
            pokemons.append(self.redis.hgetall("pm:%s:%s" % (self.userid, pokemon_uid)))
        return pokemons


    # Get all data for a user's Pokedex
    def get_all(self):
        pokedex = self.redis.smembers("pokedex:%s" % self.userid)
        if len(pokedex) == 0:
            return
        pokemons = []
        for pokemon_uid in pokedex:
            pokemons.append(self.redis.hgetall("pm:%s:%s" % (self.userid, pokemon_uid)))
        return pokemons

    # Update one Pokemon data
    def update_one(self, p_pokemon_uid, p_pokemon_data):
        if self.redis.sismember("pm:%s:%s" % (self.userid, p_pokemon_uid)):
            self.redis.hmset(
                    "pm:%s:%s" % (self.userid, pokemon_uid), # Hash Key
                    p_pokemon_data                           # Mapping
                    #"box",         p_pokemon_data['box'],
                    #"status",      p_pokemon_data['status'],
                    #"happiness",   p_pokemon_data['happiness'],
                    #"level",       p_pokemon_data['level'],
                    #"fourMoves",   p_pokemon_data['fourMoves'],
                    #"maxStats",    p_pokemon_data['maxStats'],
                    #"currHP",      p_pokemon_data['currHP'],
                    #"p_currEXP",   p_pokemon_data['currEXP'],
                    #"toNextLevel", p_pokemon_data['toNextLevel'],
                    #"memo",        p_pokemon_data['memo']
                    )
            return True
        else:
            return False


    # Add new tamed Pokemon
    def add(self, p_pokemon_data):
        if self.redis.sadd("pokedex:%s" % self.userid, p_pokemon_data["uid"]):
            #pokemon_uid = self.redis.incr("u:%s" % self.userid, "pokemons")
            pokemon_uid = self.redis.incr("u:%s:p" % self.userid)
            self.redis.hmset("pm:%s:%s" % (self.userid, pokemon_uid), p_pokemon_data)
            return True
        else:
            return False


#
# RESTs
#
@server.route('/')
def index():
    r = redis.Redis(RADIS_HOST, REDIS_PORT, REDIS_DB)
    r.setnx('global:nextUserid', 0)
    return 'PMService is Running'

# For Debug
@server.route('/debug')
def debug():
    r = redis.Redis(RADIS_HOST, REDIS_PORT, REDIS_DB)
    output = '<html>'
    # USER
    userids = r.smembers("users")
    output += 'USERs:</br>'
    for userid in userids:
        user = User(userid).get()
        chart = '<tr>#ID:'          + user['id']          + ' </tr>' \
                '<tr>_Name:'        + user['name']        + ' </tr>' \
                '<tr>_TimeStarted:' + user['timeStarted'] + ' </tr>' \
                '<tr>_Money:'       + user['money']       + ' </tr>' \
                '<tr>_Badges:'      + user['badges']      + ' </tr>' \
                '<tr>_SixPokemons:' + user['sixPokemons'] + ' </tr>' \
                '<tr>_Pokedex:'     + user['pokedex']     + ' </tr>' \
                '<tr>_Pokemons:'    + user['pokemons']    + ' </tr>' \
                '<tr>_Bag:'         + user['bag']         + ' </tr>' \
                '</br>'
        output += chart

        # USER's POKEMON
        pokemon = Pokemon(userid)
        output += '</br>USER:' + userid + ' - SIXPOKEMONs:</br>'
        sixpokemons = pokemon.get_six()
        if type(sixpokemons) is list:
            for p in sixpokemons:
                chart = '<tr>#UID:'        + str(p['uid'])         + ' </tr>' \
                        '<tr>_SID:'        + str(p['sid'])         + ' </tr>' \
                        '<tr>_box:'        + str(p['box'])         + ' </tr>' \
                        '<tr>_status:'     + str(p['status'])      + ' </tr>' \
                        '<tr>_gender:'     + str(p['gender'])      + ' </tr>' \
                        '<tr>_happiness:'  + str(p['happiness'])   + ' </tr>' \
                        '<tr>_level:'      + str(p['level'])       + ' </tr>' \
                        '<tr>_fourMoves:'  + p['fourMoves']        + ' </tr>' \
                        '<tr>_maxStats:'   + p['maxStats']         + ' </tr>' \
                        '<tr>_currHP:'     + str(p['currHP'])      + ' </tr>' \
                        '<tr>_currEXP:'    + str(p['currEXP'])     + ' </tr>' \
                        '<tr>toNextLevel:' + str(p['toNextLevel']) + ' </tr>' \
                        '<tr>memo:'        + p['memo']             + ' </tr>' \
                        '</br>'
                output += chart

        # USER's POKEDEX
        output += '</br>USER:' + userid + ' - POKEDEX:</br>'
        pokedex = pokemon.get_all()
        if type(pokedex) is list:
            for p in pokedex:
                chart = '<tr>#UID:'        + str(p['uid'])         + ' </tr>' \
                        '<tr>_SID:'        + str(p['sid'])         + ' </tr>' \
                        '<tr>_box:'        + str(p['box'])         + ' </tr>' \
                        '<tr>_status:'     + str(p['status'])      + ' </tr>' \
                        '<tr>_gender:'     + str(p['gender'])      + ' </tr>' \
                        '<tr>_happiness:'  + str(p['happiness'])   + ' </tr>' \
                        '<tr>_level:'      + str(p['level'])       + ' </tr>' \
                        '<tr>_fourMoves:'  + p['fourMoves']        + ' </tr>' \
                        '<tr>_maxStats:'   + p['maxStats']         + ' </tr>' \
                        '<tr>_currHP:'     + str(p['currHP'])      + ' </tr>' \
                        '<tr>_currEXP:'    + str(p['currEXP'])     + ' </tr>' \
                        '<tr>toNextLevel:' + str(p['toNextLevel']) + ' </tr>' \
                        '<tr>memo:'        + p['memo']             + ' </tr>' \
                        '</br>'
                output += chart
    output += '</html>'
    return output

#
# User Section
#
# User - GET <userid>, if valid, return user's id
@server.get('/id')
def get_userid():
    header = Header(request.headers)
    if not header.auth():
        return False
    openID = OpenID(header.get_provider(), header.get_identity())
    userid = None
    # If authenticated, get the <userid>
    if openID.authenticate():
        userid = openID.authorized_user()
    # Else, add a new OpenID for a new user
    else:
        userid = openID.add()
    return {'userID':userid}

# User - GET if valid, return user's data
# u: User
@server.get('/u')
def get_user():
    header = Header(request.headers)
    if not header.auth():
        return False
    openID = OpenID(header.get_provider(), header.get_identity())
    userid = None
    # If authenticated, get the <userid>
    if openID.authenticate():
        userid = openID.authorized_user()
    # Else, add a new OpenID for a new user
    else:
        userid = openID.add()
    # Return user data if the <userid> is valid
    if userid:
        return User(userid).get()
    else:
        return False

# User - POST with <name>, check uniqueness for it
# cu: Check Uniqueness
@server.post('/cu')
def get_user():
    header = Header(request.headers)
    if not header.auth():
        return {'u':-1}
    openID = OpenID(header.get_provider(), header.get_identity())
    userid = None
    # If authenticated, get the <userid>
    if openID.authenticate():
        userid = openID.authorized_user()
    # Else, add a new OpenID for a new user
    else:
        userid = openID.add()
    # Return result whether <name> is unique
    uniqueness = -1
    if userid:
        # If ture, means exist, return 0
        if User(userid).check_name_uniqueness(request.params.get("name")):
            uniqueness = 0
        else:
            uniqueness = 1
    else:
        uniqueness = -1
    return {'u':uniqueness}

# User - POST Data
# uu: Update User
@server.post('/uu')
def update_user():
    header = Header(request.headers)
    if not header.auth():
        return False
    openID = OpenID(header.get_provider(), header.get_identity())
    # If authenticated, update user data
    if openID.authenticate():
        data = request.params
        userdata = {}
        for key in data.keys():
            userdata[key] = data.get(key)
        if User(openID.authorized_user()).update(userdata):
            return {'v':1}
    return {'v':0}


# User - GET Pokemon
# pm: PokeMon
@server.get('/pm/<pokemon_uid:int>')
def user_pokemon(pokemon_uid):
    header = Header(request.headers)
    if not header.auth():
        return False
    openID = OpenID(header.get_provider(), header.get_identity())
    if openID.authenticate():
        return Pokemon(openID.authorized_user()).get_one(pokemon_uid)

# User - GET Six Pokemons
# 6pm: Six PokeMons
@server.get('/6pm')
def user_sixpokemons():
    header = Header(request.headers)
    if not header.auth():
        return False
    openID = OpenID(header.get_provider(), header.get_identity())
    if openID.authenticate():
        return {"sixPokemons":Pokemon(openID.authorized_user()).get_six()}

# User - GET Pokedex
# pd: PokeDex
@server.get('/pd')
def user_pokedex():
    header = Header(request.headers)
    if not header.auth():
        return False
    openID = OpenID(header.get_provider(), header.get_identity())
    if openID.authenticate():
        return {"pokedex":Pokemon(openID.authorized_user()).get_all()}

# User - POST Pokemon
# upm: Update PokeMon
@server.post('/upm')
def user_pokemon():
    header = Header(request.headers)
    if not header.auth():
        return False
    openID = OpenID(header.get_provider(), header.get_identity())
    if openID.authenticate():
        data = request.params
        pokemon_data = {}
        for key in data.keys():
            pokemon_data[key] = data.get(key)
        Pokemon(openID.authorized_user()).add(pokemon_data)
    else:
        return False


#
# Pokemon Section
#
# Pokemon - Area
@server.route('/pokemon/<id:int>/area')
def pokemon_area(id):
    pass

# Region - Wild Pokemons
# wpm: Wild PokeMon
@server.route('/wpm')
def user_pokedex():
    header = Header(request.headers)
    region = header.get_region()
    pokedex = { 'wildpokemons' : [
        {'uid':1, 'sid':1, 'level':10},
        {'uid':2, 'sid':2, 'level':10},
        {'uid':3, 'sid':3, 'level':10},
        {'uid':4, 'sid':4, 'level':10},
        {'uid':5, 'sid':5, 'level':10},
        {'uid':6, 'sid':6, 'level':10},
        {'uid':7, 'sid':7, 'level':10},
        {'uid':8, 'sid':8, 'level':10},
        {'uid':9, 'sid':9, 'level':10},
        {'uid':10, 'sid':10, 'level':10}]}
    return pokedex


#
# Start a server instance
#
run(
        server,                 # Run Bottle() instance: |server|
        host     = 'localhost',
        port     = 8080,
        reloader = True,        # restarts the server every time edit a module file
        debug    = True         # Comment out it before deploy
        )
