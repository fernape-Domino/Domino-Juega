# models.py
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()


class Player(db.Model):
    __tablename__ = "players"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    active = db.Column(db.Boolean, default=True)

    def __repr__(self):
        return f"<Player {self.name}>"


class Team(db.Model):
    __tablename__ = "teams"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)

    player1_id = db.Column(db.Integer, db.ForeignKey("players.id"), nullable=False)
    player2_id = db.Column(db.Integer, db.ForeignKey("players.id"), nullable=False)

    player1 = db.relationship("Player", foreign_keys=[player1_id])
    player2 = db.relationship("Player", foreign_keys=[player2_id])

    # Estadísticas acumuladas (opcional pero útil)
    games_played = db.Column(db.Integer, default=0)
    games_won = db.Column(db.Integer, default=0)
    games_lost = db.Column(db.Integer, default=0)
    points_for = db.Column(db.Integer, default=0)
    points_against = db.Column(db.Integer, default=0)

    def __repr__(self):
        return f"<Team {self.name}>"


class Match(db.Model):
    __tablename__ = "matches"
    id = db.Column(db.Integer, primary_key=True)

    team_a_id = db.Column(db.Integer, db.ForeignKey("teams.id"), nullable=False)
    team_b_id = db.Column(db.Integer, db.ForeignKey("teams.id"), nullable=False)

    team_a = db.relationship("Team", foreign_keys=[team_a_id], backref="matches_as_a")
    team_b = db.relationship("Team", foreign_keys=[team_b_id], backref="matches_as_b")

    target_score = db.Column(db.Integer, default=100)
    score_a = db.Column(db.Integer, default=0)
    score_b = db.Column(db.Integer, default=0)

    winner_team_id = db.Column(db.Integer, db.ForeignKey("teams.id"), nullable=True)
    winner_team = db.relationship("Team", foreign_keys=[winner_team_id], backref="wins")

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    finished_at = db.Column(db.DateTime, nullable=True)

    def __repr__(self):
        return f"<Match {self.id}>"


class Round(db.Model):
    __tablename__ = "rounds"
    id = db.Column(db.Integer, primary_key=True)
    match_id = db.Column(db.Integer, db.ForeignKey("matches.id"), nullable=False)
    number = db.Column(db.Integer, nullable=False)

    points_team_a = db.Column(db.Integer, default=0)
    points_team_b = db.Column(db.Integer, default=0)

    match = db.relationship("Match", backref="rounds")

    def __repr__(self):
        return f"<Round {self.number} - Match {self.match_id}>"
