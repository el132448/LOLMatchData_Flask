from . import db
from sqlalchemy.sql import func
from sqlalchemy import Table, text, select, or_
from flask import flash
import time, requests, datetime, pandas as pd

class System(db.Model):
    id = db.Column(db.Integer, primary_key=True, unique=True)
    last_update_time = db.Column(db.String(1000), unique=True)

class Player(db.Model):
    id = db.Column(db.Integer, primary_key=True, unique=True)
    summoner_name = db.Column(db.String(1000), unique=True)
    tag_line = db.Column(db.String(100))
    region = db.Column(db.String(100))
    mass_region = db.Column(db.String(100))
    queue_id = db.Column(db.Integer)
    puuid = db.Column(db.String(100), unique=True)

    def __init__(self, id, summoner_name, tag_line, region, mass_region, queue_id, puuid):
        self.id = id
        self.summoner_name = summoner_name
        self.tag_line = tag_line
        self.region = region
        self.mass_region = mass_region
        self.queue_id = queue_id
        self.puuid = puuid

        # with default value
        self.no_games = 100
        self.api_key = 'RGAPI-d0df3f5e-06ee-4b76-ac3c-a2c93d3651aa'
        self.startTime = 1623801600 # 2021.06.16 00:00:00
        self.endTime = int(time.time())
        self.df = pd.DataFrame() # empty DataFrame
        self.stat = {}
        self.match_ids_list = []
        self.last_match_num_db = 0

        print(f'{summoner_name} with id = {id} has been instantiated')

    def get_match_ids(self):
        print("=========================get_match_ids============================")
        # get matchId from database
        table_name = f'player_{self.id}'
        db_matchId = query_table_by_name(table_name)
        len_matchId = len(db_matchId)
        if len_matchId > 0: # match data already in database
            self.last_match_num_db = db_matchId[len_matchId-1][0] # which is also the id of the match data in db
            last_matchId = db_matchId[len_matchId-1][1]
            print(f'last match in db for {self.summoner_name} is id = {self.last_match_num_db}, matchId = {last_matchId}')
        else:
            last_matchId = "null"
        
        i = 0
        while i < 100: # max 10000 match which is impossible
            if self.queue_id == 0: # all type of match
                queue = ""
            else:
                queue = f'queue={str(self.queue_id)}&'

            api_url = (
                "https://" + self.mass_region + ".api.riotgames.com/lol/match/v5/matches/by-puuid/" +
                self.puuid + "/ids?" + queue + "start=" + str(i * 100) + 
                "&count=" + str(self.no_games) + "&api_key=" + self.api_key)
            resp = requests.get(api_url)
            match_ids = resp.json()
            print(f'getting {self.summoner_name}\'s match_ids set {i}, result:{str(resp)}')

            # Rate Limit hit
            if resp.status_code == 429:
                print("Rate Limit hit, sleeping for 10 seconds (20 requests every 1 seconds & 100 requests every 2 minutes)")
                time.sleep(10) 
                continue # continue: start the loop again
            elif resp.status_code != 200:
                print(f'error: get_match_ids resp.status_code != 200 ')
                i = 101 # end the loop
            elif match_ids == []:
                print(f'getting {self.summoner_name}\'s match_ids, result: empty match_ids = [] (End)')
                i = 101 # end the loop
            else:
                # success, then compare the non-repeating match with the last match in db
                for match in match_ids:
                    if match == last_matchId:
                        print(f'{match} is repeating with last match in db: {self.last_match_num_db} {last_matchId}')
                        i = 101
                        break # stop checking other match
                    else:
                        # append to a list for further requesting
                        self.match_ids_list.append(match)
                # counter added => loop continue
                i = i + 1

        print(f'all {self.summoner_name}\'s match_ids get! Number of matchs in the list = {len(self.match_ids_list)}')

    def get_match_data(self, match_id):
        api_url = (
            "https://" + self.mass_region + ".api.riotgames.com/lol/match/v5/matches/" +
            match_id + "?api_key=" + self.api_key)
        
        while True:
            resp = requests.get(api_url)

            if resp.status_code == 429:
                print("Rate Limit hit, sleeping for 10 seconds (20 requests every 1 seconds & 100 requests every 2 minutes)")
                time.sleep(10)
                continue
            elif resp.status_code != 200:
                break # end the loop
            elif resp.status_code == 200:
                match_data = resp.json()
                print(f'data in {match_id} got!')
                return match_data
            else:
                break # end the loop
        
    def insert_match_data_to_database(self, match_data, match_num):
        match_id = match_data['metadata']['matchId']
        print(f'Gathering {self.summoner_name}\'s match data of {match_id}')

        id = match_num

        # get player_data from a match ID
        participants = match_data['metadata']['participants']
        player_index = participants.index(self.puuid)
        # extract infomation from match_data
        start_time = round(match_data['info']['gameStartTimestamp']/1000)
        date = str(datetime.datetime.fromtimestamp(start_time))[:10]
        time = str(datetime.datetime.fromtimestamp(start_time))[10:]

        # empty match data for special case: TW2_92712884
        if match_data['info']['participants'] == []:
            length = "0"
            queueId = 0
            game_version = "0"
            team = "null"
            win = 0
            early_surrender = 0
            surrender = 0
            summoner_name = self.summoner_name
            summoner_level = 0
            champion = "null"
            kills = 0
            deaths = 0
            assists = 0
            KDA = 0
            quadra_kills = 0
            penta_kills = 0
            damage_to_champions = 0
            damage_taken = 0
            gold_earned = 0
            minions_killed = 0
        else:
            player_data = match_data['info']['participants'][player_index]

            length = str(datetime.timedelta(seconds=int(match_data['info']['gameDuration'])))
            queueId = match_data['info']['queueId']
            game_version = match_data['info']['gameVersion']
            team = 'blue' if player_data['teamId'] == 100 else 'red'
            win = 1 if player_data['win'] else 0
            early_surrender = 1 if player_data["gameEndedInEarlySurrender"] else 0
            surrender = 1 if player_data["gameEndedInSurrender"] else 0
            summoner_name = player_data['summonerName']
            summoner_level = player_data['summonerLevel']
            champion = player_data['championName']
            kills = player_data['kills']
            deaths = player_data['deaths']
            assists = player_data['assists']
            if deaths != 0:
                KDA = round((kills+assists)/deaths, 2)
            elif deaths == 0:
                KDA = kills+assists
            quadra_kills = player_data['quadraKills']
            penta_kills = player_data['pentaKills']
            damage_to_champions = player_data['totalDamageDealtToChampions']
            damage_taken = player_data['totalDamageTaken']
            gold_earned = player_data['goldEarned']
            minions_killed = player_data['totalMinionsKilled']
        
        # add them to data
        data_to_insert = [
            id,match_id,date,start_time,time,length,queueId,game_version,team,win,early_surrender,
            surrender,summoner_name,summoner_level,champion,kills,deaths,assists,KDA,
            quadra_kills,penta_kills,damage_to_champions,damage_taken,gold_earned,minions_killed
            ]
        print(f'data_to_insert.id = "{data_to_insert[0]}", match_id = {data_to_insert[1]}')

        # insert_data_by_table_name
        table_name = f'player_{self.id}'

        with db.engine.connect() as connection:
            table = Table(table_name, db.Model.metadata, autoload_with=connection)
            # Create an insert statement
            insert_statement = table.insert().values(data_to_insert)

            # Execute the insert statement using db.session
            db.session.execute(insert_statement)
            db.session.commit()

    

def get_puuid(summoner_name, tag_line, region):
    api_url = ("https://"+ region + ".api.riotgames.com/riot/account/v1/accounts/by-riot-id/" + summoner_name + "/" + tag_line + "?api_key=RGAPI-d0df3f5e-06ee-4b76-ac3c-a2c93d3651aa")
    resp = requests.get(api_url)

    player_info = resp.json()
    puuid = player_info['puuid']
    print('puuid get!')
    return puuid

def instantiate_all_player():
    player_table = Player.query.all()
    player_list = []
    for player in player_table:
        player_obj = Player(player.id, player.summoner_name, player.tag_line, player.region, player.mass_region, player.queue_id, player.puuid)
        player_list.append(player_obj)
    # print(f'player_list={player_list}')
    return player_list

def query_table_by_name(table_name, filters=None):
        with db.engine.connect() as connection:
            # 使用 db.metadata.tables.get(table_name) 取得表物件
            table = Table(table_name, db.Model.metadata, autoload_with=connection)

            # 創建查詢
            query = table.select()

            # 添加過濾條件 e.g. filter_conditions = [f"matchId  = '{match_id}'"]
            if filters:
                filter_conditions = [text(condition) for condition in filters]
                query = query.where(or_(*filter_conditions))

            # 執行查詢並獲取結果
            result = connection.execute(query).fetchall()
            # print(f'select {filters} from table: {table_name}, result = {bool(result)}')

            return result
        

# dynamic create table when add player
def create_player_table(id):
    table_name = f'player_{id}'
    if table_name not in db.metadata.tables:
        dynamic_table_class = type(table_name, (db.Model,), {
                'id': db.Column(db.Integer, primary_key=True, unique=True),
                'matchId': db.Column(db.String(100), unique=True),
                'date': db.Column(db.String(100)),
                'start_time': db.Column(db.String(100)),
                'date': db.Column(db.String(100)),
                'time': db.Column(db.String(100)),
                'length': db.Column(db.String(100)),
                'queueId':  db.Column(db.Integer),
                'game_version': db.Column(db.String(100)),
                'team': db.Column(db.String(100)),
                'win': db.Column(db.String(100)),
                'early_surrender': db.Column(db.String(100)),
                'surrender': db.Column(db.String(100)),
                'summoner_name': db.Column(db.String(100)),
                'summoner_level': db.Column(db.Integer),
                'champion': db.Column(db.String(100)),
                'kills': db.Column(db.Integer),
                'deaths': db.Column(db.Integer),
                'deaths': db.Column(db.Integer),
                'assists': db.Column(db.Integer),
                'KDA': db.Column(db.Float(100)),
                'quadra_kills': db.Column(db.Integer),
                'penta_kills': db.Column(db.Integer),
                'damage_to_champions': db.Column(db.Integer),
                'damage_taken': db.Column(db.Integer),
                'gold_earned': db.Column(db.Integer),
                'minions_killed': db.Column(db.Integer),
                })
            # __table_args__ = {'extend_existing': True} 
        return dynamic_table_class
    else:
        flash("Table exist.", category='error')
        return None

