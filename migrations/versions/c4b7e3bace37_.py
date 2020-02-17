"""empty message

Revision ID: c4b7e3bace37
Revises: c4351663e2fc
Create Date: 2020-02-03 20:29:03.683958

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c4b7e3bace37'
down_revision = 'c4351663e2fc'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('variant_naliva_for_trip', sa.Column('trip_number', sa.Integer(), nullable=True))
    op.add_column('variant_sliva_for_trip', sa.Column('trip_number', sa.Integer(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('variant_sliva_for_trip', 'trip_number')
    op.drop_column('variant_naliva_for_trip', 'trip_number')
    # ### end Alembic commands ###