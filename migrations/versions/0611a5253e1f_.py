"""empty message

Revision ID: 0611a5253e1f
Revises: 
Create Date: 2019-07-15 14:49:59.534693

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0611a5253e1f'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('azs_list',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('number', sa.Integer(), nullable=True),
    sa.Column('active', sa.Boolean(), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('number')
    )
    op.create_table('user',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('username', sa.String(length=64), nullable=True),
    sa.Column('email', sa.String(length=120), nullable=True),
    sa.Column('password_hash', sa.String(length=128), nullable=True),
    sa.Column('role', sa.String(length=60), nullable=True),
    sa.Column('about_me', sa.String(length=140), nullable=True),
    sa.Column('last_seen', sa.DateTime(), nullable=True),
    sa.Column('token', sa.String(length=32), nullable=True),
    sa.Column('token_expiration', sa.DateTime(), nullable=True),
    sa.Column('last_message_read_time', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_user_email'), 'user', ['email'], unique=True)
    op.create_index(op.f('ix_user_token'), 'user', ['token'], unique=True)
    op.create_index(op.f('ix_user_username'), 'user', ['username'], unique=True)
    op.create_table('cfg_db_connection',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('azs_id', sa.Integer(), nullable=True),
    sa.Column('system_type', sa.String(length=140), nullable=True),
    sa.Column('ip_address', sa.String(length=240), nullable=True),
    sa.Column('port', sa.Integer(), nullable=True),
    sa.Column('username', sa.String(length=120), nullable=True),
    sa.Column('password', sa.String(length=120), nullable=True),
    sa.ForeignKeyConstraint(['azs_id'], ['azs_list.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('followers',
    sa.Column('follower_id', sa.Integer(), nullable=True),
    sa.Column('followed_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['followed_id'], ['user.id'], ),
    sa.ForeignKeyConstraint(['follower_id'], ['user.id'], )
    )
    op.create_table('message',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('sender_id', sa.Integer(), nullable=True),
    sa.Column('recipient_id', sa.Integer(), nullable=True),
    sa.Column('body', sa.String(length=140), nullable=True),
    sa.Column('timestamp', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['recipient_id'], ['user.id'], ),
    sa.ForeignKeyConstraint(['sender_id'], ['user.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_message_timestamp'), 'message', ['timestamp'], unique=False)
    op.create_table('notification',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=128), nullable=True),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('timestamp', sa.Float(), nullable=True),
    sa.Column('payload_json', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_notification_name'), 'notification', ['name'], unique=False)
    op.create_index(op.f('ix_notification_timestamp'), 'notification', ['timestamp'], unique=False)
    op.create_table('post',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('body', sa.String(length=140), nullable=True),
    sa.Column('timestamp', sa.DateTime(), nullable=True),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('language', sa.String(length=5), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_post_timestamp'), 'post', ['timestamp'], unique=False)
    op.create_table('tanks',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('azs_id', sa.Integer(), nullable=True),
    sa.Column('tank_number', sa.Integer(), nullable=True),
    sa.Column('fuel_type', sa.Integer(), nullable=True),
    sa.Column('nominal_capacity', sa.Float(), nullable=True),
    sa.Column('real_capacity', sa.Float(), nullable=True),
    sa.Column('corrected_capacity', sa.Float(), nullable=True),
    sa.Column('capacity', sa.Float(), nullable=True),
    sa.Column('drain_time', sa.Integer(), nullable=True),
    sa.Column('after_drain_time', sa.Integer(), nullable=True),
    sa.Column('mixing', sa.Boolean(), nullable=True),
    sa.Column('active', sa.Boolean(), nullable=True),
    sa.ForeignKeyConstraint(['azs_id'], ['azs_list.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('tank_number')
    )
    op.create_table('task',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('name', sa.String(length=128), nullable=True),
    sa.Column('description', sa.String(length=128), nullable=True),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('complete', sa.Boolean(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_task_name'), 'task', ['name'], unique=False)
    op.create_table('fuel_realisation',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('shop_id', sa.Integer(), nullable=True),
    sa.Column('tank_id', sa.Integer(), nullable=True),
    sa.Column('product_code', sa.Integer(), nullable=True),
    sa.Column('fuel_level', sa.Float(), nullable=True),
    sa.Column('fuel_volume', sa.Float(), nullable=True),
    sa.Column('fuel_temperature', sa.Float(), nullable=True),
    sa.Column('datetime', sa.DateTime(), nullable=True),
    sa.Column('download_time', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['tank_id'], ['tanks.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_fuel_realisation_shop_id'), 'fuel_realisation', ['shop_id'], unique=False)
    op.create_table('fuel_residue',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('shop_id', sa.Integer(), nullable=True),
    sa.Column('tank_id', sa.Integer(), nullable=True),
    sa.Column('product_code', sa.Integer(), nullable=True),
    sa.Column('fuel_level', sa.Float(), nullable=True),
    sa.Column('fuel_volume', sa.Float(), nullable=True),
    sa.Column('fuel_temperature', sa.Float(), nullable=True),
    sa.Column('datetime', sa.DateTime(), nullable=True),
    sa.Column('download_time', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['shop_id'], ['azs_list.id'], ),
    sa.ForeignKeyConstraint(['tank_id'], ['tanks.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('fuel_residue')
    op.drop_index(op.f('ix_fuel_realisation_shop_id'), table_name='fuel_realisation')
    op.drop_table('fuel_realisation')
    op.drop_index(op.f('ix_task_name'), table_name='task')
    op.drop_table('task')
    op.drop_table('tanks')
    op.drop_index(op.f('ix_post_timestamp'), table_name='post')
    op.drop_table('post')
    op.drop_index(op.f('ix_notification_timestamp'), table_name='notification')
    op.drop_index(op.f('ix_notification_name'), table_name='notification')
    op.drop_table('notification')
    op.drop_index(op.f('ix_message_timestamp'), table_name='message')
    op.drop_table('message')
    op.drop_table('followers')
    op.drop_table('cfg_db_connection')
    op.drop_index(op.f('ix_user_username'), table_name='user')
    op.drop_index(op.f('ix_user_token'), table_name='user')
    op.drop_index(op.f('ix_user_email'), table_name='user')
    op.drop_table('user')
    op.drop_table('azs_list')
    # ### end Alembic commands ###
