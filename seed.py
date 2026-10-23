import os
import random
from datetime import date, timedelta

from app import app, db, User, Event, EventDate, Signup, _hash_pw

ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin")

NAMES = ["Carlos", "Ana", "Luis", "María", "Jorge", "Laura", "Pedro", "Sofía", "Diego", "Valeria", "Andrés", "Camila", "Fernando", "Gabriela", "Ricardo", "Daniela", "Miguel", "Lucía", "José", "Patricia"]

EVENTS_DATA = [
    {
        "title": "Defensa de Proyecto",
        "description": "Turno de presentación final del proyecto de integración.",
        "allow_multiple_signups": True,
        "show_attendees_publicly": True,
        "dates": [
            ("2026-10-24", "10:00", "11:00", 3),
            ("2026-10-24", "14:00", "15:00", 3),
            ("2026-10-25", "09:00", "10:00", 2),
        ]
    },
    {
        "title": "Taller de UX Móvil",
        "description": "Diseño de interfaces para dispositivos móviles con Material 3.",
        "allow_multiple_signups": False,
        "show_attendees_publicly": True,
        "dates": [
            ("2026-10-26", "09:00", "11:00", 5),
            ("2026-10-26", "14:00", "16:00", 5),
        ]
    },
    {
        "title": "Reunión de Departamento",
        "description": "Reunión mensual de coordinación.",
        "allow_multiple_signups": False,
        "show_attendees_publicly": False,
        "dates": [
            ("2026-10-27", "08:30", "09:30", 10),
        ]
    },
    {
        "title": "Sesión de Fotos",
        "description": "Sesión fotográfica para anuario.",
        "allow_multiple_signups": True,
        "show_attendees_publicly": True,
        "dates": [
            ("2026-10-28", "10:00", "11:00", 2),
            ("2026-10-28", "11:00", "12:00", 2),
            ("2026-10-28", "12:00", "13:00", 2),
        ]
    },
    {
        "title": "Examen Parcial",
        "description": "Examen parcial de la materia.",
        "allow_multiple_signups": False,
        "show_attendees_publicly": False,
        "dates": [
            ("2026-10-29", "08:00", "10:00", 8),
            ("2026-10-29", "10:00", "12:00", 8),
        ]
    },
]

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        # Ensure admin exists
        admin = User.query.filter_by(is_admin=True).first()
        if not admin:
            admin = User(username=ADMIN_USERNAME, password_hash=_hash_pw(ADMIN_PASSWORD), is_admin=True, must_change_password=False)
            db.session.add(admin)
            db.session.commit()

        # Create regular users
        users = []
        for name in NAMES:
            u = User.query.filter_by(username=name).first()
            if not u:
                u = User(username=name, password_hash=_hash_pw("1234"), must_change_password=False)
                db.session.add(u)
                db.session.commit()
            users.append(u)

        # Create events, dates, and signups
        for ed in EVENTS_DATA:
            ev = Event(
                title=ed["title"],
                description=ed["description"],
                allow_multiple_signups=ed["allow_multiple_signups"],
                show_attendees_publicly=ed["show_attendees_publicly"],
            )
            db.session.add(ev)
            db.session.commit()

            for date_str, t, et, spots in ed["dates"]:
                y, m, d = map(int, date_str.split("-"))
                edate = EventDate(event_id=ev.id, date=date(y, m, d), time=t, end_time=et, max_spots=spots)
                db.session.add(edate)
                db.session.commit()

                # Randomly fill spots
                random.shuffle(users)
                for u in users[:spots]:
                    try:
                        s = Signup(user_id=u.id, event_date_id=edate.id)
                        db.session.add(s)
                        db.session.commit()
                    except Exception:
                        db.session.rollback()

        print(f"Seed complete: {len(users)} users, {len(EVENTS_DATA)} events.")
        print(f"Admin: {ADMIN_USERNAME} / {ADMIN_PASSWORD}")
        print("Users PIN: 1234")
