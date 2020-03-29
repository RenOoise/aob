"""empty message

Revision ID: ed462492167d
Revises: f7f1e32ddd65
Create Date: 2019-08-23 13:40:45.364063

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = 'ed462492167d'
down_revision = 'f7f1e32ddd65'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('work_type',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('type', sa.String(length=600), nullable=True),
    sa.Column('active', sa.Boolean(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('truck_false',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('truck_id', sa.Integer(), nullable=True),
    sa.Column('azs_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['azs_id'], ['azs_list.id'], ),
    sa.ForeignKeyConstraint(['truck_id'], ['trucks.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.drop_table('pma__recent')
    op.drop_table('pma__favorite')
    op.drop_table('pma__navigationhiding')
    op.drop_table('pma__pdf_pages')
    op.drop_table('pma__column_info')
    op.drop_table('pma__tracking')
    op.drop_table('pma__table_info')
    op.drop_table('pma__usergroups')
    op.drop_table('pma__table_coords')
    op.drop_table('pma__userconfig')
    op.drop_table('pma__central_columns')
    op.drop_table('pma__bookmark')
    op.drop_table('pma__table_uiprefs')
    op.drop_table('pma__history')
    op.drop_table('pma__users')
    op.drop_table('pma__relation')
    op.drop_table('pma__designer_settings')
    op.drop_table('pma__export_templates')
    op.drop_table('pma__savedsearches')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('pma__savedsearches',
    sa.Column('id', mysql.INTEGER(display_width=5, unsigned=True), nullable=False),
    sa.Column('username', mysql.VARCHAR(collation='utf8_bin', length=64), server_default=sa.text("''"), nullable=False),
    sa.Column('db_name', mysql.VARCHAR(collation='utf8_bin', length=64), server_default=sa.text("''"), nullable=False),
    sa.Column('search_name', mysql.VARCHAR(collation='utf8_bin', length=64), server_default=sa.text("''"), nullable=False),
    sa.Column('search_data', mysql.TEXT(collation='utf8_bin'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    mysql_collate='utf8_bin',
    mysql_comment='Saved searches',
    mysql_default_charset='utf8',
    mysql_engine='InnoDB'
    )
    op.create_table('pma__export_templates',
    sa.Column('id', mysql.INTEGER(display_width=5, unsigned=True), nullable=False),
    sa.Column('username', mysql.VARCHAR(collation='utf8_bin', length=64), nullable=False),
    sa.Column('export_type', mysql.VARCHAR(collation='utf8_bin', length=10), nullable=False),
    sa.Column('template_name', mysql.VARCHAR(collation='utf8_bin', length=64), nullable=False),
    sa.Column('template_data', mysql.TEXT(collation='utf8_bin'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    mysql_collate='utf8_bin',
    mysql_comment='Saved export templates',
    mysql_default_charset='utf8',
    mysql_engine='InnoDB'
    )
    op.create_table('pma__designer_settings',
    sa.Column('username', mysql.VARCHAR(collation='utf8_bin', length=64), nullable=False),
    sa.Column('settings_data', mysql.TEXT(collation='utf8_bin'), nullable=False),
    sa.PrimaryKeyConstraint('username'),
    mysql_collate='utf8_bin',
    mysql_comment='Settings related to Designer',
    mysql_default_charset='utf8',
    mysql_engine='InnoDB'
    )
    op.create_table('pma__relation',
    sa.Column('master_db', mysql.VARCHAR(collation='utf8_bin', length=64), server_default=sa.text("''"), nullable=False),
    sa.Column('master_table', mysql.VARCHAR(collation='utf8_bin', length=64), server_default=sa.text("''"), nullable=False),
    sa.Column('master_field', mysql.VARCHAR(collation='utf8_bin', length=64), server_default=sa.text("''"), nullable=False),
    sa.Column('foreign_db', mysql.VARCHAR(collation='utf8_bin', length=64), server_default=sa.text("''"), nullable=False),
    sa.Column('foreign_table', mysql.VARCHAR(collation='utf8_bin', length=64), server_default=sa.text("''"), nullable=False),
    sa.Column('foreign_field', mysql.VARCHAR(collation='utf8_bin', length=64), server_default=sa.text("''"), nullable=False),
    sa.PrimaryKeyConstraint('master_db', 'master_table', 'master_field'),
    mysql_collate='utf8_bin',
    mysql_comment='Relation table',
    mysql_default_charset='utf8',
    mysql_engine='InnoDB'
    )
    op.create_table('pma__users',
    sa.Column('username', mysql.VARCHAR(collation='utf8_bin', length=64), nullable=False),
    sa.Column('usergroup', mysql.VARCHAR(collation='utf8_bin', length=64), nullable=False),
    sa.PrimaryKeyConstraint('username', 'usergroup'),
    mysql_collate='utf8_bin',
    mysql_comment='Users and their assignments to user groups',
    mysql_default_charset='utf8',
    mysql_engine='InnoDB'
    )
    op.create_table('pma__history',
    sa.Column('id', mysql.BIGINT(display_width=20, unsigned=True), nullable=False),
    sa.Column('username', mysql.VARCHAR(collation='utf8_bin', length=64), server_default=sa.text("''"), nullable=False),
    sa.Column('db', mysql.VARCHAR(collation='utf8_bin', length=64), server_default=sa.text("''"), nullable=False),
    sa.Column('table', mysql.VARCHAR(collation='utf8_bin', length=64), server_default=sa.text("''"), nullable=False),
    sa.Column('timevalue', mysql.TIMESTAMP(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.Column('sqlquery', mysql.TEXT(collation='utf8_bin'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    mysql_collate='utf8_bin',
    mysql_comment='SQL history for phpMyAdmin',
    mysql_default_charset='utf8',
    mysql_engine='InnoDB'
    )
    op.create_table('pma__table_uiprefs',
    sa.Column('username', mysql.VARCHAR(collation='utf8_bin', length=64), nullable=False),
    sa.Column('db_name', mysql.VARCHAR(collation='utf8_bin', length=64), nullable=False),
    sa.Column('table_name', mysql.VARCHAR(collation='utf8_bin', length=64), nullable=False),
    sa.Column('prefs', mysql.TEXT(collation='utf8_bin'), nullable=False),
    sa.Column('last_update', mysql.TIMESTAMP(), server_default=sa.text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'), nullable=False),
    sa.PrimaryKeyConstraint('username', 'db_name', 'table_name'),
    mysql_collate='utf8_bin',
    mysql_comment="Tables' UI preferences",
    mysql_default_charset='utf8',
    mysql_engine='InnoDB'
    )
    op.create_table('pma__bookmark',
    sa.Column('id', mysql.INTEGER(display_width=11), nullable=False),
    sa.Column('dbase', mysql.VARCHAR(collation='utf8_bin', length=255), server_default=sa.text("''"), nullable=False),
    sa.Column('user', mysql.VARCHAR(collation='utf8_bin', length=255), server_default=sa.text("''"), nullable=False),
    sa.Column('label', mysql.VARCHAR(charset='utf8', length=255), server_default=sa.text("''"), nullable=False),
    sa.Column('query', mysql.TEXT(collation='utf8_bin'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    mysql_collate='utf8_bin',
    mysql_comment='Bookmarks',
    mysql_default_charset='utf8',
    mysql_engine='InnoDB'
    )
    op.create_table('pma__central_columns',
    sa.Column('db_name', mysql.VARCHAR(collation='utf8_bin', length=64), nullable=False),
    sa.Column('col_name', mysql.VARCHAR(collation='utf8_bin', length=64), nullable=False),
    sa.Column('col_type', mysql.VARCHAR(collation='utf8_bin', length=64), nullable=False),
    sa.Column('col_length', mysql.TEXT(collation='utf8_bin'), nullable=True),
    sa.Column('col_collation', mysql.VARCHAR(collation='utf8_bin', length=64), nullable=False),
    sa.Column('col_isNull', mysql.TINYINT(display_width=1), autoincrement=False, nullable=False),
    sa.Column('col_extra', mysql.VARCHAR(collation='utf8_bin', length=255), server_default=sa.text("''"), nullable=True),
    sa.Column('col_default', mysql.TEXT(collation='utf8_bin'), nullable=True),
    sa.PrimaryKeyConstraint('db_name', 'col_name'),
    mysql_collate='utf8_bin',
    mysql_comment='Central list of columns',
    mysql_default_charset='utf8',
    mysql_engine='InnoDB'
    )
    op.create_table('pma__userconfig',
    sa.Column('username', mysql.VARCHAR(collation='utf8_bin', length=64), nullable=False),
    sa.Column('timevalue', mysql.TIMESTAMP(), server_default=sa.text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'), nullable=False),
    sa.Column('config_data', mysql.TEXT(collation='utf8_bin'), nullable=False),
    sa.PrimaryKeyConstraint('username'),
    mysql_collate='utf8_bin',
    mysql_comment='User preferences storage for phpMyAdmin',
    mysql_default_charset='utf8',
    mysql_engine='InnoDB'
    )
    op.create_table('pma__table_coords',
    sa.Column('db_name', mysql.VARCHAR(collation='utf8_bin', length=64), server_default=sa.text("''"), nullable=False),
    sa.Column('table_name', mysql.VARCHAR(collation='utf8_bin', length=64), server_default=sa.text("''"), nullable=False),
    sa.Column('pdf_page_number', mysql.INTEGER(display_width=11), server_default=sa.text("'0'"), autoincrement=False, nullable=False),
    sa.Column('x', mysql.FLOAT(unsigned=True), server_default=sa.text("'0'"), nullable=False),
    sa.Column('y', mysql.FLOAT(unsigned=True), server_default=sa.text("'0'"), nullable=False),
    sa.PrimaryKeyConstraint('db_name', 'table_name', 'pdf_page_number'),
    mysql_collate='utf8_bin',
    mysql_comment='Table coordinates for phpMyAdmin PDF output',
    mysql_default_charset='utf8',
    mysql_engine='InnoDB'
    )
    op.create_table('pma__usergroups',
    sa.Column('usergroup', mysql.VARCHAR(collation='utf8_bin', length=64), nullable=False),
    sa.Column('tab', mysql.VARCHAR(collation='utf8_bin', length=64), nullable=False),
    sa.Column('allowed', mysql.ENUM('Y', 'N', collation='utf8_bin'), server_default=sa.text("'N'"), nullable=False),
    sa.PrimaryKeyConstraint('usergroup', 'tab', 'allowed'),
    mysql_collate='utf8_bin',
    mysql_comment='User groups with configured menu items',
    mysql_default_charset='utf8',
    mysql_engine='InnoDB'
    )
    op.create_table('pma__table_info',
    sa.Column('db_name', mysql.VARCHAR(collation='utf8_bin', length=64), server_default=sa.text("''"), nullable=False),
    sa.Column('table_name', mysql.VARCHAR(collation='utf8_bin', length=64), server_default=sa.text("''"), nullable=False),
    sa.Column('display_field', mysql.VARCHAR(collation='utf8_bin', length=64), server_default=sa.text("''"), nullable=False),
    sa.PrimaryKeyConstraint('db_name', 'table_name'),
    mysql_collate='utf8_bin',
    mysql_comment='Table information for phpMyAdmin',
    mysql_default_charset='utf8',
    mysql_engine='InnoDB'
    )
    op.create_table('pma__tracking',
    sa.Column('db_name', mysql.VARCHAR(collation='utf8_bin', length=64), nullable=False),
    sa.Column('table_name', mysql.VARCHAR(collation='utf8_bin', length=64), nullable=False),
    sa.Column('version', mysql.INTEGER(display_width=10, unsigned=True), autoincrement=False, nullable=False),
    sa.Column('date_created', mysql.DATETIME(), nullable=False),
    sa.Column('date_updated', mysql.DATETIME(), nullable=False),
    sa.Column('schema_snapshot', mysql.TEXT(collation='utf8_bin'), nullable=False),
    sa.Column('schema_sql', mysql.TEXT(collation='utf8_bin'), nullable=True),
    sa.Column('data_sql', mysql.LONGTEXT(collation='utf8_bin'), nullable=True),
    sa.Column('tracking', mysql.SET(collation='utf8_bin', length=15), nullable=True),
    sa.Column('tracking_active', mysql.INTEGER(display_width=1, unsigned=True), server_default=sa.text("'1'"), autoincrement=False, nullable=False),
    sa.PrimaryKeyConstraint('db_name', 'table_name', 'version'),
    mysql_collate='utf8_bin',
    mysql_comment='Database changes tracking for phpMyAdmin',
    mysql_default_charset='utf8',
    mysql_engine='InnoDB'
    )
    op.create_table('pma__column_info',
    sa.Column('id', mysql.INTEGER(display_width=5, unsigned=True), nullable=False),
    sa.Column('db_name', mysql.VARCHAR(collation='utf8_bin', length=64), server_default=sa.text("''"), nullable=False),
    sa.Column('table_name', mysql.VARCHAR(collation='utf8_bin', length=64), server_default=sa.text("''"), nullable=False),
    sa.Column('column_name', mysql.VARCHAR(collation='utf8_bin', length=64), server_default=sa.text("''"), nullable=False),
    sa.Column('comment', mysql.VARCHAR(charset='utf8', length=255), server_default=sa.text("''"), nullable=False),
    sa.Column('mimetype', mysql.VARCHAR(charset='utf8', length=255), server_default=sa.text("''"), nullable=False),
    sa.Column('transformation', mysql.VARCHAR(collation='utf8_bin', length=255), server_default=sa.text("''"), nullable=False),
    sa.Column('transformation_options', mysql.VARCHAR(collation='utf8_bin', length=255), server_default=sa.text("''"), nullable=False),
    sa.Column('input_transformation', mysql.VARCHAR(collation='utf8_bin', length=255), server_default=sa.text("''"), nullable=False),
    sa.Column('input_transformation_options', mysql.VARCHAR(collation='utf8_bin', length=255), server_default=sa.text("''"), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    mysql_collate='utf8_bin',
    mysql_comment='Column information for phpMyAdmin',
    mysql_default_charset='utf8',
    mysql_engine='InnoDB'
    )
    op.create_table('pma__pdf_pages',
    sa.Column('db_name', mysql.VARCHAR(collation='utf8_bin', length=64), server_default=sa.text("''"), nullable=False),
    sa.Column('page_nr', mysql.INTEGER(display_width=10, unsigned=True), nullable=False),
    sa.Column('page_descr', mysql.VARCHAR(charset='utf8', length=50), server_default=sa.text("''"), nullable=False),
    sa.PrimaryKeyConstraint('page_nr'),
    mysql_collate='utf8_bin',
    mysql_comment='PDF relation pages for phpMyAdmin',
    mysql_default_charset='utf8',
    mysql_engine='InnoDB'
    )
    op.create_table('pma__navigationhiding',
    sa.Column('username', mysql.VARCHAR(collation='utf8_bin', length=64), nullable=False),
    sa.Column('item_name', mysql.VARCHAR(collation='utf8_bin', length=64), nullable=False),
    sa.Column('item_type', mysql.VARCHAR(collation='utf8_bin', length=64), nullable=False),
    sa.Column('db_name', mysql.VARCHAR(collation='utf8_bin', length=64), nullable=False),
    sa.Column('table_name', mysql.VARCHAR(collation='utf8_bin', length=64), nullable=False),
    sa.PrimaryKeyConstraint('username', 'item_name', 'item_type', 'db_name', 'table_name'),
    mysql_collate='utf8_bin',
    mysql_comment='Hidden items of navigation tree',
    mysql_default_charset='utf8',
    mysql_engine='InnoDB'
    )
    op.create_table('pma__favorite',
    sa.Column('username', mysql.VARCHAR(collation='utf8_bin', length=64), nullable=False),
    sa.Column('tables', mysql.TEXT(collation='utf8_bin'), nullable=False),
    sa.PrimaryKeyConstraint('username'),
    mysql_collate='utf8_bin',
    mysql_comment='Favorite tables',
    mysql_default_charset='utf8',
    mysql_engine='InnoDB'
    )
    op.create_table('pma__recent',
    sa.Column('username', mysql.VARCHAR(collation='utf8_bin', length=64), nullable=False),
    sa.Column('tables', mysql.TEXT(collation='utf8_bin'), nullable=False),
    sa.PrimaryKeyConstraint('username'),
    mysql_collate='utf8_bin',
    mysql_comment='Recently accessed tables',
    mysql_default_charset='utf8',
    mysql_engine='InnoDB'
    )
    op.drop_table('truck_false')
    op.drop_table('work_type')
    # ### end Alembic commands ###
