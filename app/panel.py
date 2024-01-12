from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from .models import Player, System, create_player_table, query_table_by_name, instantiate_all_player, get_puuid
from . import db
from sqlalchemy import Table, update
import threading
from datetime import datetime

panel_blueprint = Blueprint('panel_blueprint', __name__, template_folder="templates/panel", static_folder="static")

button_disabled = False

@panel_blueprint.route('/panel/', methods=['GET', 'POST'])
def panel():
    system = System.query.all()
    if system:
        last_update_time = system[0].last_update_time
    else:
        # create the data in table
        last_update_time = 0
        create_update_time = System(id=1,last_update_time=last_update_time)
        db.session.add(create_update_time)
        db.session.commit()
    return render_template('update.html', last_update_time=last_update_time)

def master_update_function():
    global button_disabled
    # instantiate all player from database & get a list of all player
    player_list = instantiate_all_player()
    for player in player_list:
        # get a list of matchs to be run
        player.get_match_ids()
        # last match num of a player in db
        match_num = len(player.match_ids_list) + player.last_match_num_db

        for match_id in player.match_ids_list:
            # check if the match id is exist in database already
            table_name = f'player_{player.id}'
            filter_conditions = [f"matchId  = '{match_id}'"]
            result = query_table_by_name(table_name, filters=filter_conditions)

            # if result = False: matchId not in table insert match data to database
            if not result:
                match_data = player.get_match_data(match_id)
                player.insert_match_data_to_database(match_data, match_num)
            
            # counter
            match_num -= 1
    
    # finish function => button enable
    button_disabled = False

    # update last update time in database
    system = System.query.all()
    now = datetime.now()
    dt_string = now.strftime("%Y-%m-%d %H:%M:%S")
    if system: # False when no player info in db
        system[0].last_update_time = dt_string
        db.session.commit()
        print(f"All match data is updated at {dt_string}!")

@panel_blueprint.route('/panel/update/', methods=['GET', 'POST'])
def panel_update():
    global button_disabled
    # if button is not disabled, run the update function
    if not button_disabled:
        button_disabled = True
        threading.Thread(target=master_update_function()).start()
        return jsonify(result='success')
    else:
        return jsonify(result='busy')

@panel_blueprint.route('/button_status', methods=['GET'])
def button_status():
    global button_disabled
    return jsonify(button_disabled=button_disabled)

@panel_blueprint.route('/panel/add_player/', methods=['GET', 'POST'])
def panel_add_player():
    db_player = Player.query.all()

    if request.method == 'POST':
        # add player
        id = request.form.get('id')
        summoner_name = request.form.get('summoner_name')
        tag_line = request.form.get('tag_line')
        region = request.form.get('region')
        mass_region = request.form.get('mass_region')
        queue_id = request.form.get('queue_id')
        puuid = get_puuid(summoner_name, tag_line, region)

        # check if player already exist
        check_player_exist = Player.query.filter_by(summoner_name=summoner_name).first()
        if check_player_exist:
            flash("Player already exists.", category='error')
        else:
            # add player to table player
            new_player = Player(id=id,summoner_name=summoner_name, tag_line=tag_line, region=region, mass_region=mass_region, queue_id=queue_id, puuid=puuid)
            db.session.add(new_player)
            db.session.commit()

            # create new table for new player
            create_player_table(new_player.id)
            db.create_all()

        return redirect(url_for('.panel_add_player'))
    
    return render_template('add_player.html', db_player=db_player)
