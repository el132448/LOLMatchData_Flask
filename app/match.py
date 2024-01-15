from . import db
from flask import Blueprint, render_template, redirect, url_for, request
from .models import Player, Team, query_table_by_name
import pandas as pd
from datetime import datetime

match_blueprint = Blueprint('match_blueprint', __name__, template_folder="templates/match")

@match_blueprint.route("/", methods=['GET', 'POST'])
def base():
    return render_template('home.html')

# All stat
@match_blueprint.route('/match/', methods=['GET', 'POST'])
def match():
    
    # ===========All part==========
    # combine all players' table to a big dataFrame
    df = pd.DataFrame() # initialise an empty df
    for player in Player.query.all():
        if player.id > 7: # match all only for first 7 player
            break
        table_name = f'player_{player.id}'
        player = query_table_by_name(table_name, [f"queueId  = '450'"])
        new_df = pd.DataFrame(player)
        # concat together
        df = pd.concat([df, new_df], axis="rows")
    
    # change win to int for groupby mean
    df = df.replace({'win': {"1": 1, "0": 0}})
    if not df.empty:
        # groupby champion
        df = df.groupby("champion").agg(
            **{
                "count": pd.NamedAgg(column="win", aggfunc="count"),
                "win": pd.NamedAgg(column="win", aggfunc="sum"),
                "win rate": pd.NamedAgg(column="win", aggfunc="mean"),
                })
        
        # insert 'lose' in between 'win' and 'win rate'
        df_lose = df['count'] - df['win']
        df.insert(2, 'lose', df_lose)
        
        # add a Total row
        all_total = df.sum()
        # adjust sum to mean for Total row
        all_total.iloc[3] = all_total.iloc[1] / all_total.iloc[0]
        # add Total row to the table
        df.loc['< TOTAL >'] = all_total
        
        # data modify
        df['win rate'] = (df['win rate'] * 100).round(1)
        
        # ==========Player part==========
        # store the total 'count' for further pick rate calculation
        total_df_count = df['count']
        
        for player in Player.query.all():
            if player.id > 7: # match all only for first 7 player
                break
            table_name = f'player_{player.id}'
            player_match = query_table_by_name(table_name, [f"queueId  = '450'"])

            new_df = pd.DataFrame(player_match)
            # change win to int for mean
            new_df = new_df.replace({'win': {"1": 1, "0": 0}})

            # groupby champion
            new_df = new_df.groupby("champion").agg(
                **{
                    "count": pd.NamedAgg(column="win", aggfunc="count"),
                    "win": pd.NamedAgg(column="win", aggfunc="sum"),
                    "win rate": pd.NamedAgg(column="win", aggfunc="mean"),
                    })
            
            # insert 'lose' in between 'win' and 'win rate'
            new_df_lose = new_df['count'] - new_df['win']
            new_df.insert(2, 'lose', new_df_lose)

            # add a Total row
            total = new_df.sum()
            # adjust sum to mean for Total row
            total.iloc[3] = total.iloc[1] / total.iloc[0]
            # add Total row to the table
            new_df.loc['< TOTAL >'] = total
            
            # # insert 'pick rate' in between 'count' and 'win'
            new_df = new_df.fillna(0)
            index_to_insert = new_df.columns.get_loc('win')
            df_pick_rate = (new_df['count'] / total_df_count * 100).round(1)
            new_df.insert(index_to_insert, 'pick rate', df_pick_rate)

            # data modify
            new_df['win rate'] = (new_df['win rate'] * 100).round(1)
            
            # concat together
            df = pd.concat([df, new_df], axis="columns")


        # change all NaN to 0
        df = df.fillna(0)
        df['count'] = df['count'].astype(int)
        df['win'] = df['win'].astype(int)
        df['lose'] = df['lose'].astype(int)
        
        # move 'champion' up 1 row
        df = df.reset_index()

        # add player name on the top of table by MultiIndex
        name_array = ["","All","All","All","All"]
        for player in Player.query.all():
            if player.id > 7: # match all only for first 7 player
                break
            for i in range(1, 6):
                name_array.append(player.summoner_name)
                i = i + 1
        df.columns = pd.MultiIndex.from_arrays([name_array,df.columns])

        df = df.to_html()
    else:
        df = "df is empty: no match data in db!"
        print("df is empty: no match data in db!")
    return render_template('match.html',df=df, player_list=Player.query.all())

def groupby_matchId_champion():
    # get the df of ARAM of 7 player
    df = pd.DataFrame()
    for i in range(1,8): # player_1 to _7
        table_name = f'player_{i}'
        table = query_table_by_name(table_name, ['"queueId" = 450'])
        new_df = pd.DataFrame(table)
        df = pd.concat([df,new_df], axis=0)

    # groupby matchId
    df = df.groupby('matchId').apply(lambda x: pd.Series({
        'summoner_names': ', '.join(x['summoner_name']),
        'champions': ', '.join(x['champion']),
        'win': ','.join(x['win']),
        })).reset_index()
    
    # remove the game not played by 5 of us
    matchId_drop_list = []
    for index, row in df.iterrows():
        if row.iloc[2].count(", ") < 4:
            matchId_drop_list.append(row.iloc[0])
            row_index = df.index[df['matchId'] == row.iloc[0]].tolist()
            df = df.drop(row_index[0])

    # adjust 0,0,0,0,0 and 1,1,1,1,1 to 0 and 1
    df['win'] = df['win'].str.split(',').apply(lambda x: sum(map(int, x)))
    df['win'] = (df['win'] / 5).astype(int)

    return df

def get_team_type_win_rate():
    df = groupby_matchId_champion()
    # team type: Fighter, Tank, Mage, Assassin, Marksman, Support
    team_tag_list =[]
    for index, row in df.iterrows():
        champ_name_list = row.iloc[2].split(", ")
        tag1_list = []
        for champ in champ_name_list:
            if champ == 'FiddleSticks':
                champ = 'Fiddlesticks'
            if champ == 'null':
                continue
            filter_conditions = [f"name  = '{champ}'"]
            query_champ = query_table_by_name('champion', filters=filter_conditions)
            tag1_list.append(query_champ[0][2])
            
        # make a string to combine
        count_Fighter = tag1_list.count('Fighter')
        count_Tank = tag1_list.count('Tank')
        count_Mage = tag1_list.count('Mage')
        count_Assassin = tag1_list.count('Assassin')
        count_Marksman = tag1_list.count('Marksman')
        count_Support = tag1_list.count('Support')

        if count_Fighter == 0: str_Fighter = ""
        else: str_Fighter = f'{count_Fighter}鬥士 '
        if count_Tank == 0: str_Tank = ""
        else: str_Tank = f'{count_Tank}坦克 '
        if count_Mage == 0: str_Mage = ""
        else: str_Mage = f'{count_Mage}法師 '
        if count_Assassin == 0: str_Assassin = ""
        else: str_Assassin = f'{count_Assassin}刺客 '
        if count_Marksman == 0: str_Marksman = ""
        else: str_Marksman = f'{count_Marksman}射手 '
        if count_Support == 0: str_Support = ""
        else: str_Support = f'{count_Support}輔助 '

        team_tag = f'{str_Fighter}{str_Tank}{str_Mage}{str_Assassin}{str_Marksman}{str_Support}'
        if team_tag == '1Tank ':
            print(row.iloc[0])
            print(team_tag)
        team_tag_list.append(team_tag)

    df.insert(3, "team type", team_tag_list, True)

    # groupby team type
    df = df.groupby("team type").agg(
                **{
                    "count": pd.NamedAgg(column="win", aggfunc="count"),
                    "win": pd.NamedAgg(column="win", aggfunc="sum"),
                    "win rate": pd.NamedAgg(column="win", aggfunc="mean"),
                    })
    
    df['win rate'] = (df['win rate'] * 100) .round(2)
    df['count'] = df['count'].astype('int')

    df = df.reset_index()

    # write into db
    df.to_sql(name='team', con=db.engine, if_exists='replace', index_label='id')

# by team type
@match_blueprint.route('/match/team_type/', methods=['GET', 'POST'])
def match_team_type():
    df = pd.read_sql('team', con=db.engine)
    
    if request.method == 'POST':
        selected_value = int(request.form['filterValue'])
        df['count'] = df['count'].astype('int')
        df = df[df['count'] > selected_value]
    
    df = df.to_html()

    return render_template('match_team_type.html', df=df, player_list=Player.query.all())

# All match team stat
@match_blueprint.route('/match/team/', methods=['GET', 'POST'])
def match_team():
    df = groupby_matchId_champion()
    df = df.to_html() 
    return render_template('match_team.html', df=df, player_list=Player.query.all())

# get all player's match data into one list
def get_all_player_match():
    # combine all players' table
    db_player = Player.query.all()
    db_player_list = []
    for player in db_player:
        if player.id > 7: # match all only for first 7 player
            break
        table_name = f'player_{player.id}'
        db_player_match = query_table_by_name(table_name)
        db_player_list.append(db_player_match)
    return db_player_list

# All match data
@match_blueprint.route('/match/data/', methods=['GET', 'POST'])
def match_data():
    db_player_list = get_all_player_match()
    return render_template('match_data.html', db_player_list=db_player_list, player_list=Player.query.all())

# get win_rate_data
def get_win_rate_data(db_player_match):
    db_player_match
    df = pd.DataFrame(db_player_match)

    # win is varchar -> int
    df = df.replace({'win': {"1": 1, "0": 0}})
    df["summoner_name"] = "name"
    df = df.groupby("summoner_name").expanding().mean(numeric_only=True)['win']
    win_rate_data = []
    for winRate in df:
        winRate = int(winRate*10000)/100
        win_rate_data.append(winRate)
    time_data_str = []
    for match in db_player_match:
        time_data_str.append(match.date)

    # delete first few item for removing win rate start from 0
    del win_rate_data[:10]
    del time_data_str[:10]

    time_data = time_data_str
    # time_data = [datetime.strptime(date_str, "%Y-%m-%d") for date_str in time_data_str]
    # print(time_data, win_rate_data)
    return time_data, win_rate_data

# player stat
@match_blueprint.route('/match/<player_name>/', methods=['GET', 'POST'])
def match_player_stat(player_name):
    # check if the player exist in table player
    player = Player.query.filter_by(summoner_name=player_name).first()
    if not player: # player not found, redirect to match
        print("player not found")
        df = f'no match data of {player_name} in db!'
        player = player_name
    else: # player found
        # query the table
        table_name = f'player_{player.id}'

        # filter game mode
        if request.method == 'POST':
            selected_game_modes = request.form.getlist('game_modes[]')
            conditions = [f"queueId  = '{mode}'" for mode in selected_game_modes]
            db_player_match = query_table_by_name(table_name, conditions)
        else:
            filter = [f"queueId  = '450'"] # default ARAM
            db_player_match = query_table_by_name(table_name, filter)
    
        if db_player_match: # not empty match data in db
            # create the dataframe
            df_raw = pd.DataFrame(db_player_match)
            df = df_raw
            # change win to int for mean
            df = df.replace({'win': {"1": 1, "0": 0}})

            # groupby champion
            df = df.groupby("champion").agg(
                **{
                    "count": pd.NamedAgg(column="win", aggfunc="count"),
                    "win": pd.NamedAgg(column="win", aggfunc="sum"),
                    "win rate": pd.NamedAgg(column="win", aggfunc="mean"),
                    "kills": pd.NamedAgg(column="kills", aggfunc="mean"),
                    "deaths": pd.NamedAgg(column="deaths", aggfunc="mean"),
                    "assists": pd.NamedAgg(column="assists", aggfunc="mean"),
                    "KDA": pd.NamedAgg(column="KDA", aggfunc="mean"),
                    "quadra kills": pd.NamedAgg(column="quadra_kills", aggfunc="sum"),
                    "penta kills": pd.NamedAgg(column="penta_kills", aggfunc="sum"),
                    "damage to champ": pd.NamedAgg(column="damage_to_champions", aggfunc="mean"),
                    "damage taken": pd.NamedAgg(column="damage_taken", aggfunc="mean"),
                    "gold earned": pd.NamedAgg(column="gold_earned", aggfunc="mean"),
                    "minions killed": pd.NamedAgg(column="minions_killed", aggfunc="mean")
                    })

            # insert 'lose' in between 'win' and 'win rate'
            index_to_insert = df.columns.get_loc('win rate')
            df_lose = df['count'] - df['win']
            df.insert(index_to_insert, 'lose', df_lose)

            # add a Total row
            total = df.sum()
            # adjust sum to mean for Total row
            total.iloc[3] = total.iloc[1] / total.iloc[0]
            for i in range(4,14):
                if i == 8 or i == 9:
                    continue
                else:
                    column_name = df_raw.columns[i+11]
                    column_sum = df_raw[column_name].sum()
                    total.iloc[i] = column_sum / total.iloc[0]
            # calculate KDA
            total.iloc[7] = (total.iloc[4] + total.iloc[6]) / total.iloc[5]
            # add Total row to the table
            df.loc['< TOTAL >'] = total

            # insert 'pick rate' in between 'count' and 'win'
            index_to_insert = df.columns.get_loc('win')
            df_pick_rate = (df['count'] / total.iloc[0] * 100).round(1)
            df.insert(index_to_insert, 'pick rate', df_pick_rate)

            # reset index to move champion to the first row
            df = df.reset_index()

            # data modify
            df['count'] = df['count'].astype(int)
            df['win'] = df['win'].astype(int)
            df['lose'] = df['lose'].astype(int)
            df['win rate'] = (df['win rate'] * 100).round(1)
            # round decimal
            for i in range(5,15):
                column_name = df.columns[i]
                df[column_name] = (df[column_name] * 100).astype(int)
                df[column_name] = df[column_name] / 100
                df[column_name] = df[column_name].round(1)

            # print to html
            df = df.to_html()
        else:
            print("player not found")
            df = f'no match data of {player_name} in db!'
            # player = player_name
        time_data, win_rate_data = get_win_rate_data(db_player_match)
        # print(time_data, win_rate_data)

    return render_template('player.html', player=player, df=df, player_list=Player.query.all(), time_data=time_data, win_rate_data=win_rate_data)

# player data
@match_blueprint.route('/match/<player_name>/data/', methods=['GET', 'POST'])
def match_player_data(player_name):
    # check if the player exist in table player
    player = Player.query.filter_by(summoner_name=player_name).first()

    if not player: # player not found, redirect to match
        print("player not found")
        return redirect(url_for('.match'))
    else: # player found
        table_name = f'player_{player.id}'
        db_player_match = query_table_by_name(table_name)
        return render_template('player_data.html', player=player, db_player_match=db_player_match, player_list=Player.query.all())
