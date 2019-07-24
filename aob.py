from app import create_app, db, cli
from app.models import User, Post, Message, Notification, Task
from apscheduler.schedulers.background import BackgroundScheduler
from app import tasks
import atexit


def download_tanks_info():
    print("!!!!!!@!")


scheduler = BackgroundScheduler()
scheduler.add_job(func=download_tanks_info, trigger="interval", seconds=5)
scheduler.start()

app = create_app()
cli.register(app)


@app.shell_context_processor
def make_shell_context():
    return {'db': db, 'User': User, 'Post': Post, 'Message': Message,
            'Notification': Notification, 'Task': Task}
