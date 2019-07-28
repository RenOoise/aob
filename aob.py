from app import create_app, db, cli
from app.models import User, Post, Message, Notification, Task
from apscheduler.schedulers.background import BackgroundScheduler
from app import tasks
import atexit


def test():
    tasks.download_tanks_info(1)


scheduler = BackgroundScheduler()
scheduler.add_job(func=test, trigger="interval", minutes=7)
scheduler.start()

app = create_app()
cli.register(app)


@app.shell_context_processor
def make_shell_context():
    return {'db': db, 'User': User, 'Post': Post, 'Message': Message,
            'Notification': Notification, 'Task': Task}
