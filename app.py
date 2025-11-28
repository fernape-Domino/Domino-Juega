# app.py
from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory
from models import db, Player, Team, Match, Round
from datetime import datetime
import os


def create_app():
    app = Flask(__name__)

    # --- CONFIGURACIÓN ---
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///domino_juega.db"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SECRET_KEY"] = "super-secret-key"

    db.init_app(app)

    # Crear BD si no existe
    with app.app_context():
        db.create_all()

    # ---------------------------------------------------------
    #                      RUTAS PRINCIPALES
    # ---------------------------------------------------------

    @app.route("/")
    def index():
        total_players = Player.query.count()
        total_teams = Team.query.count()
        total_matches = Match.query.count()
        last_matches = Match.query.order_by(Match.created_at.desc()).limit(5).all()

        # Detectar partida en curso
        ongoing_match = (
            Match.query
            .filter_by(winner_team_id=None)
            .order_by(Match.created_at.desc())
            .first()
        )

        return render_template(
            "index.html",
            total_players=total_players,
            total_teams=total_teams,
            total_matches=total_matches,
            last_matches=last_matches,
            ongoing_match=ongoing_match,
        )

    # ---------------------------------------------------------
    #                      JUGADORES
    # ---------------------------------------------------------

    @app.route("/players", methods=["GET", "POST"])
    def players():
        if request.method == "POST":
            name = request.form.get("name")

            if not name.strip():
                flash("El nombre es obligatorio.", "danger")
                return redirect(url_for("players"))

            player = Player(name=name.strip())
            db.session.add(player)

            try:
                db.session.commit()
                flash("Jugador agregado.", "success")
            except:
                db.session.rollback()
                flash("Error: ese nombre ya existe.", "danger")

            return redirect(url_for("players"))

        players_list = Player.query.order_by(Player.name).all()
        return render_template("players.html", players=players_list)

    @app.route("/players/<int:player_id>/toggle_active", methods=["POST"])
    def toggle_player_active(player_id):
        player = Player.query.get_or_404(player_id)
        player.active = not player.active
        db.session.commit()
        return redirect(url_for("players"))

    @app.route("/players/<int:player_id>/delete", methods=["POST"])
    def delete_player(player_id):
        player = Player.query.get_or_404(player_id)

        # No se puede borrar si pertenece a un equipo
        teams_count = Team.query.filter(
            (Team.player1_id == player.id) | (Team.player2_id == player.id)
        ).count()

        if teams_count > 0:
            flash("No se puede eliminar: pertenece a un equipo.", "danger")
            return redirect(url_for("players"))

        db.session.delete(player)
        db.session.commit()
        flash("Jugador eliminado.", "success")
        return redirect(url_for("players"))

    # ---------------------------------------------------------
    #                      EQUIPOS
    # ---------------------------------------------------------

    @app.route("/teams", methods=["GET", "POST"])
    def teams():
        players_list = Player.query.filter_by(active=True).order_by(Player.name).all()

        if request.method == "POST":
            p1 = request.form.get("player1_id")
            p2 = request.form.get("player2_id")
            name = request.form.get("name")

            if not p1 or not p2:
                flash("Selecciona ambos jugadores.", "danger")
                return redirect(url_for("teams"))

            if p1 == p2:
                flash("No puedes repetir jugador.", "danger")
                return redirect(url_for("teams"))

            if not name.strip():
                name = f"{Player.query.get(p1).name} & {Player.query.get(p2).name}"

            team = Team(name=name.strip(), player1_id=p1, player2_id=p2)
            db.session.add(team)
            db.session.commit()
            flash("Equipo creado.", "success")
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
            flash("No se puede eliminar: equipo tiene partidas.", "danger")
            return redirect(url_for("teams"))

        db.session.delete(team)
        db.session.commit()
        flash("Equipo eliminado.", "success")
        return redirect(url_for("teams"))

    # ---------------------------------------------------------
    #                      NUEVA PARTIDA
    # ---------------------------------------------------------

    @app.route("/matches/new", methods=["GET", "POST"])
    def new_match():
        # Bloqueo si hay una partida en curso
        ongoing = Match.query.filter_by(winner_team_id=None).first()
        if ongoing:
            flash(f"Ya hay una partida en curso (# {ongoing.id}).", "warning")
            return redirect(url_for("match_detail", match_id=ongoing.id))

        teams = Team.query.order_by(Team.name).all()

        if request.method == "POST":
            a = request.form.get("team_a_id")
            b = request.form.get("team_b_id")
            target = int(request.form.get("target_score", "100"))

            if a == b:
                flash("No puedes jugar un equipo contra sí mismo.", "danger")
                return redirect(url_for("new_match"))

            match = Match(team_a_id=a, team_b_id=b, target_score=target)
            db.session.add(match)
            db.session.commit()
            flash("Partida creada.", "success")
            return redirect(url_for("match_detail", match_id=match.id))

        return render_template("new_match.html", teams=teams)

    # ---------------------------------------------------------
    #                      DETALLE DE PARTIDA
    # ---------------------------------------------------------

    @app.route("/matches/<int:match_id>", methods=["GET", "POST"])
    def match_detail(match_id):
        match = Match.query.get_or_404(match_id)

        if request.method == "POST":
            action = request.form.get("action")

            # ---------------- ELIMINAR PARTIDA ----------------
            if action == "delete":
                if match.winner_team_id is not None:
                    flash("No puedes eliminar una partida finalizada.", "danger")
                    return redirect(url_for("match_detail", match_id=match.id))

                # borrar manos primero
                for r in list(match.rounds):
                    db.session.delete(r)

                db.session.delete(match)
                db.session.commit()
                flash("Partida eliminada.", "success")
                return redirect(url_for("matches_list"))

            # ---------------- REINICIAR PARTIDA ----------------
            if action == "restart":
                if match.winner_team_id is not None:
                    flash("No puedes reiniciar una partida finalizada.", "danger")
                    return redirect(url_for("match_detail", match_id=match.id))

                for r in list(match.rounds):
                    db.session.delete(r)

                match.score_a = 0
                match.score_b = 0
                match.winner_team_id = None
                match.finished_at = None

                db.session.commit()
                flash("Partida reiniciada.", "info")
                return redirect(url_for("match_detail", match_id=match.id))

            # ---------------- MANO MANUAL ----------------
            if action == "manual":
                a = int(request.form.get("points_team_a", 0))
                b = int(request.form.get("points_team_b", 0))

            # ---------------- +30 A O B ----------------
            elif action == "plus30_a":
                a, b = 30, 0
            elif action == "plus30_b":
                a, b = 0, 30
            else:
                a = b = 0

            # Crear mano
            round_obj = Round(
                match_id=match.id,
                number=len(match.rounds) + 1,
                points_team_a=a,
                points_team_b=b
            )
            db.session.add(round_obj)

            # Actualizar marcador
            match.score_a += a
            match.score_b += b

            # Verificar ganador
            if match.winner_team_id is None:
                if match.score_a >= match.target_score or match.score_b >= match.target_score:
                    if match.score_a > match.score_b:
                        match.winner_team_id = match.team_a_id
                    else:
                        match.winner_team_id = match.team_b_id

                    match.finished_at = datetime.utcnow()

                    # Actualizar stats
                    tA = match.team_a
                    tB = match.team_b

                    tA.games_played += 1
                    tB.games_played += 1

                    tA.points_for += match.score_a
                    tA.points_against += match.score_b
                    tB.points_for += match.score_b
                    tB.points_against += match.score_a

                    if match.winner_team_id == tA.id:
                        tA.games_won += 1
                        tB.games_lost += 1
                    else:
                        tB.games_won += 1
                        tA.games_lost += 1

            db.session.commit()
            return redirect(url_for("match_detail", match_id=match.id))

        rounds = Round.query.filter_by(match_id=match.id).order_by(Round.number).all()
        return render_template("match_detail.html", match=match, rounds=rounds)

    # ---------------------------------------------------------
    #                   VER TODAS LAS PARTIDAS
    # ---------------------------------------------------------

    @app.route("/matches")
    def matches_list():
        matches = Match.query.order_by(Match.created_at.desc()).all()
        return render_template("matches.html", matches=matches)

    # ---------------------------------------------------------
    #          REINICIAR TODO EL JUEGO (GLOBAL RESET)
    # ---------------------------------------------------------

    @app.route("/reset_all", methods=["POST"])
    def reset_all():
        Round.query.delete()
        Match.query.delete()

        for t in Team.query.all():
            t.games_played = 0
            t.games_won = 0
            t.games_lost = 0
            t.points_for = 0
            t.points_against = 0

        db.session.commit()
        flash("Juego reiniciado completamente.", "warning")
        return redirect(url_for("matches_list"))

    # ---------------------------------------------------------
    #                 SERVICE WORKER PWA
    # ---------------------------------------------------------

    @app.route("/service-worker.js")
    def service_worker():
        return send_from_directory(
            os.path.join(app.root_path, "static"),
            "service-worker.js",
            mimetype="application/javascript"
        )

    return app


# PARA GUNICORN EN RENDER
app = create_app()

if __name__ == "__main__":
    app.run(debug=True, port=5005, host="0.0.0.0")
