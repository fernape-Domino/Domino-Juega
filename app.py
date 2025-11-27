# app.py
from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory
from models import db, Player, Team, Match, Round
from datetime import datetime
import os


def create_app():
    app = Flask(__name__)

    # --- CONFIGURACIÓN BÁSICA ---
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///domino_juega.db"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SECRET_KEY"] = "cambia-esta-clave"  # para mensajes flash

    db.init_app(app)

    # Crear tablas si no existen
    with app.app_context():
        db.create_all()

    # ---------------- RUTAS ----------------

    # --------- INICIO ---------
    @app.route("/")
    def index():
        total_players = Player.query.count()
        total_teams = Team.query.count()
        total_matches = Match.query.count()
        last_matches = Match.query.order_by(Match.created_at.desc()).limit(5).all()

        return render_template(
            "index.html",
            total_players=total_players,
            total_teams=total_teams,
            total_matches=total_matches,
            last_matches=last_matches,
        )

    # --------- JUGADORES ---------
    @app.route("/players", methods=["GET", "POST"])
    def players():
        if request.method == "POST":
            name = request.form.get("name")

            if not name or not name.strip():
                flash("El nombre es obligatorio.", "danger")
                return redirect(url_for("players"))

            player = Player(name=name.strip())
            db.session.add(player)

            try:
                db.session.commit()
                flash("Jugador agregado correctamente.", "success")
            except Exception:
                db.session.rollback()
                flash("Error: ese nombre ya existe o hubo un problema.", "danger")

            return redirect(url_for("players"))

        players_list = Player.query.order_by(Player.name).all()
        return render_template("players.html", players=players_list)

    @app.route("/players/<int:player_id>/toggle_active", methods=["POST"])
    def toggle_player_active(player_id):
        player = Player.query.get_or_404(player_id)
        player.active = not player.active
        db.session.commit()
        estado = "activado" if player.active else "desactivado"
        flash(f"Jugador {estado} correctamente.", "success")
        return redirect(url_for("players"))

    @app.route("/players/<int:player_id>/delete", methods=["POST"])
    def delete_player(player_id):
        player = Player.query.get_or_404(player_id)

        # Verificar si pertenece a algún equipo
        teams_count = Team.query.filter(
            (Team.player1_id == player.id) | (Team.player2_id == player.id)
        ).count()

        if teams_count > 0:
            flash("No se puede eliminar: el jugador pertenece a uno o más equipos.", "danger")
            return redirect(url_for("players"))

        db.session.delete(player)
        db.session.commit()
        flash("Jugador eliminado correctamente.", "success")
        return redirect(url_for("players"))

    # --------- EQUIPOS ---------
    @app.route("/teams", methods=["GET", "POST"])
    def teams():
        players_list = Player.query.filter_by(active=True).order_by(Player.name).all()

        if request.method == "POST":
            player1_id = request.form.get("player1_id")
            player2_id = request.form.get("player2_id")
            team_name = request.form.get("name")

            # Validaciones básicas
            if not player1_id or not player2_id:
                flash("Debes seleccionar ambos jugadores.", "danger")
                return redirect(url_for("teams"))

            if player1_id == player2_id:
                flash("Un jugador no puede estar dos veces en el mismo equipo.", "danger")
                return redirect(url_for("teams"))

            # Nombre automático si no lo escriben
            if not team_name or not team_name.strip():
                p1 = Player.query.get(player1_id)
                p2 = Player.query.get(player2_id)
                team_name = f"{p1.name} & {p2.name}"

            team = Team(
                name=team_name.strip(),
                player1_id=player1_id,
                player2_id=player2_id,
            )
            db.session.add(team)
            db.session.commit()
            flash("Equipo creado correctamente.", "success")
            return redirect(url_for("teams"))

        teams_list = Team.query.order_by(Team.name).all()
        return render_template("teams.html", teams=teams_list, players=players_list)

    @app.route("/teams/<int:team_id>/delete", methods=["POST"])
    def delete_team(team_id):
        team = Team.query.get_or_404(team_id)

        matches_count = Match.query.filter(
            (Match.team_a_id == team.id) | (Match.team_b_id == team.id)
        ).count()

        if matches_count > 0:
            flash("No se puede eliminar: el equipo tiene partidas registradas.", "danger")
            return redirect(url_for("teams"))

        db.session.delete(team)
        db.session.commit()
        flash("Equipo eliminado correctamente.", "success")
        return redirect(url_for("teams"))

    # --------- NUEVA PARTIDA ---------
    @app.route("/matches/new", methods=["GET", "POST"])
    def new_match():
        teams = Team.query.order_by(Team.name).all()

        if request.method == "POST":
            team_a_id = request.form.get("team_a_id")
            team_b_id = request.form.get("team_b_id")
            target_score = request.form.get("target_score", "100")

            if not team_a_id or not team_b_id:
                flash("Debes seleccionar ambos equipos.", "danger")
                return redirect(url_for("new_match"))

            if team_a_id == team_b_id:
                flash("No puedes jugar un equipo contra sí mismo.", "danger")
                return redirect(url_for("new_match"))

            try:
                target_score_int = int(target_score)
            except ValueError:
                target_score_int = 100

            match = Match(
                team_a_id=team_a_id,
                team_b_id=team_b_id,
                target_score=target_score_int,
            )
            db.session.add(match)
            db.session.commit()
            flash("Partida creada. ¡A jugar!", "success")
            return redirect(url_for("match_detail", match_id=match.id))

        return render_template("new_match.html", teams=teams)

    # --------- DETALLE DE PARTIDA + ANOTACIÓN ---------
    @app.route("/matches/<int:match_id>", methods=["GET", "POST"])
    def match_detail(match_id):
        match = Match.query.get_or_404(match_id)

        if request.method == "POST":
            action = request.form.get("action")

            # Lógica para determinar puntos de la mano
            if action == "manual":
                puntos_a = request.form.get("points_team_a", "0") or "0"
                puntos_b = request.form.get("points_team_b", "0") or "0"
                try:
                    puntos_a = int(puntos_a)
                    puntos_b = int(puntos_b)
                except ValueError:
                    flash("Los puntos deben ser números.", "danger")
                    return redirect(url_for("match_detail", match_id=match.id))
            elif action == "plus30_a":
                puntos_a, puntos_b = 30, 0
            elif action == "plus30_b":
                puntos_a, puntos_b = 0, 30
            else:
                puntos_a, puntos_b = 0, 0

            # Crear nueva mano
            next_number = len(match.rounds) + 1
            new_round = Round(
                match_id=match.id,
                number=next_number,
                points_team_a=puntos_a,
                points_team_b=puntos_b,
            )
            db.session.add(new_round)

            # Actualizar marcador acumulado
            match.score_a += puntos_a
            match.score_b += puntos_b

            # Verificar si alguien ganó
            if match.winner_team_id is None:
                if match.score_a >= match.target_score or match.score_b >= match.target_score:
                    if match.score_a > match.score_b:
                        match.winner_team_id = match.team_a_id
                    elif match.score_b > match.score_a:
                        match.winner_team_id = match.team_b_id
                    match.finished_at = datetime.utcnow()

                    # Actualizar estadísticas de equipos
                    team_a = match.team_a
                    team_b = match.team_b

                    team_a.games_played += 1
                    team_b.games_played += 1

                    team_a.points_for += match.score_a
                    team_a.points_against += match.score_b

                    team_b.points_for += match.score_b
                    team_b.points_against += match.score_a

                    if match.winner_team_id == team_a.id:
                        team_a.games_won += 1
                        team_b.games_lost += 1
                    elif match.winner_team_id == team_b.id:
                        team_b.games_won += 1
                        team_a.games_lost += 1

            db.session.commit()
            return redirect(url_for("match_detail", match_id=match.id))

        rounds = Round.query.filter_by(match_id=match.id).order_by(Round.number).all()
        return render_template("match_detail.html", match=match, rounds=rounds)

    # --------- HISTORIAL DE UN EQUIPO ---------
    @app.route("/teams/<int:team_id>/stats")
    def team_stats(team_id):
        team = Team.query.get_or_404(team_id)
        matches = (
            Match.query
            .filter((Match.team_a_id == team.id) | (Match.team_b_id == team.id))
            .order_by(Match.created_at.desc())
            .all()
        )
        return render_template("team_stats.html", team=team, matches=matches)

    # --------- LISTADO GENERAL DE PARTIDAS ---------
    @app.route("/matches")
    def matches_list():
        matches = Match.query.order_by(Match.created_at.desc()).all()
        return render_template("matches.html", matches=matches)

    # --------- SERVICE WORKER PWA ---------
    @app.route("/service-worker.js")
    def service_worker():
        # Servimos el service worker desde la carpeta static, pero en la raíz
        return send_from_directory(
            os.path.join(app.root_path, "static"),
            "service-worker.js",
            mimetype="application/javascript",
        )

    return app


if __name__ == "__main__":
    app = create_app()
    # host="0.0.0.0" para que el móvil pueda acceder usando la IP de la PC
    app.run(debug=True, port=5005, host="0.0.0.0")
