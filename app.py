import os
import calendar
from datetime import date, datetime, timedelta
from functools import wraps

from dotenv import load_dotenv
from flask import Flask, abort, flash, make_response, redirect, render_template, request, url_for

load_dotenv()
from flask_login import LoginManager, current_user, login_required, login_user, logout_user
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm, CSRFProtect
from werkzeug.security import check_password_hash, generate_password_hash
from weasyprint import HTML
from wtforms import BooleanField, DateField, IntegerField, PasswordField, StringField, SubmitField, TextAreaField, TimeField
from wtforms.validators import DataRequired, NumberRange, Optional, Regexp

app = Flask(__name__, template_folder="templates", static_folder="static")
def _db_uri():
    uri = os.environ.get("DATABASE_URL", "postgresql+psycopg2://scheduler:scheduler@db:5432/scheduler")
    if uri.startswith("postgresql://") and not uri.startswith("postgresql+psycopg2://"):
        uri = "postgresql+psycopg2://" + uri[len("postgresql://"):]
    return uri

app.config["SQLALCHEMY_DATABASE_URI"] = _db_uri()
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "change-me-in-production")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["WTF_CSRF_ENABLED"] = True

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"
csrf = CSRFProtect(app)


class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    must_change_password = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    signups = db.relationship("Signup", backref="user", lazy="dynamic", cascade="all, delete-orphan")

    @property
    def is_active(self):
        return True

    @property
    def is_authenticated(self):
        return True

    @property
    def is_anonymous(self):
        return False

    def get_id(self):
        return str(self.id)


class Event(db.Model):
    __tablename__ = "events"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, default="")
    allow_multiple_signups = db.Column(db.Boolean, default=False, nullable=False)
    show_attendees_publicly = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    dates = db.relationship("EventDate", backref="event", lazy="dynamic", cascade="all, delete-orphan", order_by="EventDate.date, EventDate.time")


class EventDate(db.Model):
    __tablename__ = "event_dates"
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey("events.id"), nullable=False)
    date = db.Column(db.Date, nullable=False)
    time = db.Column(db.String(20), nullable=False, default="09:00")
    end_time = db.Column(db.String(20), nullable=False, default="10:00")
    max_spots = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    signups = db.relationship("Signup", backref="event_date", lazy="dynamic", cascade="all, delete-orphan")

    @property
    def taken_spots(self):
        return self.signups.count()

    @property
    def available_spots(self):
        return max(0, self.max_spots - self.taken_spots)

    def signup_for(self, user):
        return self.signups.filter_by(user_id=user.id).first()


class Signup(db.Model):
    __tablename__ = "signups"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    event_date_id = db.Column(db.Integer, db.ForeignKey("event_dates.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint("user_id", "event_date_id", name="unique_user_event_date"),)


class LoginForm(FlaskForm):
    username = StringField("Nombre / Usuario", validators=[DataRequired()])
    password = PasswordField("PIN / Contraseña", validators=[DataRequired()])
    submit = SubmitField("Iniciar sesión")


class RegisterForm(FlaskForm):
    username = StringField("Nombre", validators=[DataRequired()])
    pin = PasswordField(
        "PIN (4 a 8 dígitos)",
        validators=[DataRequired(), Regexp(r"^\d{4,8}$", message="El PIN debe tener entre 4 y 8 dígitos numéricos")],
    )
    submit = SubmitField("Crear cuenta")


class ChangePasswordForm(FlaskForm):
    password = PasswordField("Nueva contraseña", validators=[DataRequired()])
    confirm = PasswordField("Confirmar contraseña", validators=[DataRequired()])
    submit = SubmitField("Actualizar contraseña")


class EventForm(FlaskForm):
    title = StringField("Título del evento", validators=[DataRequired()])
    description = TextAreaField("Descripción", validators=[Optional()])
    allow_multiple_signups = BooleanField("Permitir varias inscripciones por usuario")
    show_attendees_publicly = BooleanField("Mostrar asistentes públicamente")
    submit = SubmitField("Crear evento")


class EventDateForm(FlaskForm):
    date = DateField("Fecha", validators=[DataRequired()], format="%Y-%m-%d")
    time = TimeField("Hora inicio", validators=[DataRequired()], format="%H:%M")
    end_time = TimeField("Hora fin", validators=[DataRequired()], format="%H:%M")
    max_spots = IntegerField("Cupo máximo", validators=[DataRequired(), NumberRange(min=1)])
    submit = SubmitField("Agregar horario")


class UserForm(FlaskForm):
    username = StringField("Usuario", validators=[DataRequired()])
    password = PasswordField("Contraseña inicial", validators=[DataRequired()])
    submit = SubmitField("Crear usuario")


def create_admin():
    admin_username = os.environ.get("ADMIN_USERNAME", "admin").strip()
    admin_password = os.environ.get("ADMIN_PASSWORD", "admin").strip()
    admin = User.query.filter_by(is_admin=True).first()
    if not admin:
        admin = User(
            username=admin_username,
            password_hash=generate_password_hash(admin_password),
            is_admin=True,
            must_change_password=False,
        )
        db.session.add(admin)
    else:
        admin.username = admin_username
        admin.password_hash = generate_password_hash(admin_password)
    db.session.commit()


def admin_required(f):
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


MESES_ES = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
    5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
    9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre",
}
MESES_CORTO_ES = {
    1: "Ene", 2: "Feb", 3: "Mar", 4: "Abr", 5: "May", 6: "Jun",
    7: "Jul", 8: "Ago", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dic",
}
DIAS_ES = {
    0: "Lunes", 1: "Martes", 2: "Miércoles", 3: "Jueves",
    4: "Viernes", 5: "Sábado", 6: "Domingo",
}


@app.context_processor
def inject_globals():
    return {
        "md_primary": "#6750A4",
        "md_on_primary": "#FFFFFF",
        "md_surface": "#FEF7FF",
        "md_surface_variant": "#E7E0EC",
        "md_secondary": "#625B71",
        "md_error": "#B3261E",
        "meses_es": MESES_ES,
        "meses_corto_es": MESES_CORTO_ES,
        "dias_es": DIAS_ES,
    }


@app.route("/")
def index():
    if current_user.is_authenticated:
        if current_user.must_change_password:
            return redirect(url_for("change_password"))
        return redirect(url_for("admin_events") if current_user.is_admin else url_for("user_events"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data.strip()).first()
        if user and check_password_hash(user.password_hash, form.password.data):
            login_user(user, remember=True)
            if user.must_change_password:
                return redirect(url_for("change_password"))
            return redirect(url_for("index"))
        flash("Nombre o PIN/contraseña incorrectos", "error")
    return render_template("login.html", form=form)


@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    form = RegisterForm()
    if form.validate_on_submit():
        username = form.username.data.strip()
        if User.query.filter_by(username=username).first():
            flash("Ese nombre ya está registrado", "error")
        else:
            user = User(
                username=username,
                password_hash=generate_password_hash(form.pin.data.strip()),
                is_admin=False,
                must_change_password=False,
            )
            db.session.add(user)
            db.session.commit()
            login_user(user, remember=True)
            flash("Cuenta creada con éxito", "success")
            return redirect(url_for("user_events"))
    elif request.method == "POST":
        for errs in form.errors.values():
            for err in errs:
                flash(err, "error")
    return render_template("register.html", form=form)


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))


@app.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        if form.password.data != form.confirm.data:
            flash("Las contraseñas no coinciden", "error")
        elif len(form.password.data) < 4:
            flash("La contraseña debe tener al menos 4 caracteres", "error")
        else:
            current_user.password_hash = generate_password_hash(form.password.data)
            current_user.must_change_password = False
            db.session.commit()
            flash("Contraseña actualizada", "success")
            return redirect(url_for("index"))
    return render_template("change_password.html", form=form)


@app.route("/admin/events", methods=["GET", "POST"])
@admin_required
def admin_events():
    form = EventForm()
    if form.validate_on_submit():
        event = Event(
            title=form.title.data.strip(),
            description=form.description.data.strip(),
            allow_multiple_signups=form.allow_multiple_signups.data,
            show_attendees_publicly=form.show_attendees_publicly.data,
        )
        db.session.add(event)
        db.session.commit()
        flash("Evento creado", "success")
        return redirect(url_for("admin_events"))
    events = Event.query.order_by(Event.created_at.desc()).all()
    return render_template("admin_events.html", form=form, events=events, date_form_class=EventDateForm)


@app.route("/admin/events/<int:event_id>/delete", methods=["POST"])
@admin_required
def admin_delete_event(event_id):
    event = db.session.get(Event, event_id)
    if not event:
        abort(404)
    db.session.delete(event)
    db.session.commit()
    flash("Evento eliminado", "success")
    return redirect(url_for("admin_events"))


@app.route("/admin/events/<int:event_id>/dates", methods=["POST"])
@admin_required
def admin_add_event_date(event_id):
    event = db.session.get(Event, event_id)
    if not event:
        abort(404)
    form = EventDateForm(prefix=f"date_{event_id}_")
    if form.validate_on_submit():
        if form.end_time.data <= form.time.data:
            flash("La hora de fin debe ser posterior a la hora de inicio", "error")
            return redirect(url_for("admin_events"))
        event_date = EventDate(
            event_id=event_id,
            date=form.date.data,
            time=form.time.data.strftime("%H:%M"),
            end_time=form.end_time.data.strftime("%H:%M"),
            max_spots=form.max_spots.data,
        )
        db.session.add(event_date)
        db.session.commit()
        flash("Fecha y horario agregados", "success")
    else:
        flash("Fecha, horario o cupo inválidos", "error")
    return redirect(url_for("admin_events"))


@app.route("/admin/events/<int:event_id>/dates/<int:date_id>/delete", methods=["POST"])
@admin_required
def admin_delete_event_date(event_id, date_id):
    event_date = EventDate.query.filter_by(id=date_id, event_id=event_id).first()
    if not event_date:
        abort(404)
    db.session.delete(event_date)
    db.session.commit()
    flash("Fecha eliminada", "success")
    return redirect(url_for("admin_events"))


@app.route("/admin/users", methods=["GET", "POST"])
@admin_required
def admin_users():
    form = UserForm()
    if form.validate_on_submit():
        username = form.username.data.strip()
        if User.query.filter_by(username=username).first():
            flash("El usuario ya existe", "error")
        else:
            user = User(
                username=username,
                password_hash=generate_password_hash(form.password.data),
                must_change_password=True,
            )
            db.session.add(user)
            db.session.commit()
            flash("Usuario creado", "success")
        return redirect(url_for("admin_users"))
    users = User.query.filter_by(is_admin=False).order_by(User.created_at.desc()).all()
    return render_template("admin_users.html", form=form, users=users)


@app.route("/admin/users/<int:user_id>/delete", methods=["POST"])
@admin_required
def admin_delete_user(user_id):
    user = db.session.get(User, user_id)
    if not user or user.is_admin:
        abort(404)
    db.session.delete(user)
    db.session.commit()
    flash("Usuario eliminado", "success")
    return redirect(url_for("admin_users"))


def build_calendar(year, month, events, user):
    locale_calendar = calendar.Calendar(firstweekday=calendar.MONDAY)
    month_name = calendar.month_name[month]
    # Manual Spanish month names since locale may not be available
    meses = {
        1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
        5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
        9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre",
    }
    dias = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
    # Build a map of date_str -> list of event dates
    dates_by_day = {}
    for event in events:
        for ed in event.dates:
            s = ed.date.isoformat()
            dates_by_day.setdefault(s, []).append({
                "event": event,
                "date": ed,
                "signed_up": bool(ed.signup_for(user)),
            })
    for s in dates_by_day:
        dates_by_day[s].sort(key=lambda x: x["date"].time)
    weeks = []
    agenda_days = []
    for week in locale_calendar.monthdayscalendar(year, month):
        days = []
        for day in week:
            if day == 0:
                days.append(None)
            else:
                d = date(year, month, day)
                day_items = dates_by_day.get(d.isoformat(), [])
                day_obj = {
                    "day": day,
                    "date": d,
                    "is_today": d == date.today(),
                    "event_dates": day_items,
                }
                days.append(day_obj)
                if day_items:
                    agenda_days.append(day_obj)
        weeks.append(days)
    prev_month = month - 1 if month > 1 else 12
    prev_year = year if month > 1 else year - 1
    next_month = month + 1 if month < 12 else 1
    next_year = year if month < 12 else year + 1
    return {
        "year": year,
        "month": month,
        "month_name": meses[month],
        "weekday_labels": dias,
        "weeks": weeks,
        "agenda_days": agenda_days,
        "prev_year": prev_year,
        "prev_month": prev_month,
        "next_year": next_year,
        "next_month": next_month,
    }


@app.route("/events")
@login_required
def user_events():
    if current_user.is_admin:
        return redirect(url_for("admin_events"))
    events = Event.query.order_by(Event.created_at.desc()).all()
    today = date.today()
    year = request.args.get("year", today.year, type=int)
    month = request.args.get("month", today.month, type=int)
    cal = build_calendar(year, month, events, current_user)
    return render_template("user_events.html", events=events, calendar=cal)


@app.route("/events/<int:event_id>/signup", methods=["POST"])
@login_required
def signup(event_id):
    if current_user.is_admin:
        abort(403)
    event = db.session.get(Event, event_id)
    if not event:
        abort(404)
    date_id = request.form.get("date_id", type=int)
    event_date = EventDate.query.filter_by(id=date_id, event_id=event_id).first()
    if not event_date:
        abort(404)

    if not event.allow_multiple_signups:
        existing = Signup.query.join(EventDate).filter(
            Signup.user_id == current_user.id,
            EventDate.event_id == event_id,
        ).first()
        if existing:
            flash("Solo puedes inscribirte en una fecha para este evento", "error")
            return redirect(url_for("user_events"))

    if event_date.signup_for(current_user):
        flash("Ya estás inscrito en esta fecha", "error")
        return redirect(url_for("user_events"))

    if event_date.available_spots <= 0:
        flash("No hay cupos disponibles", "error")
        return redirect(url_for("user_events"))

    signup = Signup(user_id=current_user.id, event_date_id=event_date.id)
    db.session.add(signup)
    db.session.commit()
    flash("Inscripción realizada", "success")
    return redirect(url_for("user_events"))


@app.route("/mis-eventos")
@login_required
def my_events():
    if current_user.is_admin:
        return redirect(url_for("admin_events"))
    signups = (
        Signup.query
        .join(EventDate)
        .join(Event)
        .filter(Signup.user_id == current_user.id)
        .order_by(EventDate.date, EventDate.time)
        .all()
    )
    grouped = {}
    for s in signups:
        grouped.setdefault(s.event_date.event, []).append(s.event_date)
    return render_template("my_events.html", grouped=grouped)


@app.route("/admin/events/<int:event_id>/pdf")
@admin_required
def event_pdf(event_id):
    event = db.session.get(Event, event_id)
    if not event:
        abort(404)
    total_signups = sum(ed.signups.count() for ed in event.dates)
    html = render_template("event_pdf.html", event=event, total_signups=total_signups, now=datetime.utcnow())
    pdf = HTML(string=html).write_pdf()
    response = make_response(pdf)
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = f"attachment; filename=inscripciones-{event.id}.pdf"
    return response


@app.route("/signups/<int:signup_id>/cancel", methods=["POST"])
@login_required
def cancel_signup(signup_id):
    if current_user.is_admin:
        abort(403)
    signup = db.session.get(Signup, signup_id)
    if not signup or signup.user_id != current_user.id:
        abort(404)
    db.session.delete(signup)
    db.session.commit()
    flash("Inscripción cancelada", "success")
    return redirect(url_for("user_events"))


def create_app():
    with app.app_context():
        db.create_all()
        db.session.execute(db.text("ALTER TABLE event_dates ADD COLUMN IF NOT EXISTS time VARCHAR(20) NOT NULL DEFAULT '09:00'"))
        db.session.execute(db.text("ALTER TABLE event_dates ADD COLUMN IF NOT EXISTS end_time VARCHAR(20) NOT NULL DEFAULT '10:00'"))
        db.session.commit()
        create_admin()
    return app


if __name__ == "__main__":
    create_app()
    app.run(host="0.0.0.0", port=5000, debug=True)
