"""empty message

Revision ID: e26ae0c62bc1
Revises: ae07549861b9
Create Date: 2019-07-15 20:59:11.378387

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = 'e26ae0c62bc1'
down_revision = 'ae07549861b9'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('cfg_db_connection', 'system_type')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('cfg_db_connection', sa.Column('system_type', mysql.VARCHAR(collation='utf8_bin', length=140), nullable=True))
    # ### end Alembic commands ###