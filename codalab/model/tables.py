'''
The SQLAlchemy table objects for the CodaLab bundle system tables.
'''
from sqlalchemy import (
  Column,
  ForeignKey,
  Index,
  MetaData,
  Table,
  UniqueConstraint,
)
from sqlalchemy.types import (
  Integer,
  String,
  Text,
  Boolean,
  DateTime,
  Float,
)

db_metadata = MetaData()

bundle = Table(
  'bundle',
  db_metadata,
  Column('id', Integer, primary_key=True, nullable=False),
  Column('uuid', String(63), nullable=False),
  Column('bundle_type', String(63), nullable=False),
  # The command will be NULL except for run bundles.
  Column('command', Text, nullable=True),
  # The data_hash will be NULL if the bundle's value is still being computed.
  Column('data_hash', String(63), nullable=True),
  Column('state', String(63), nullable=False),
  Column('owner_id', String(255), nullable=True),
  UniqueConstraint('uuid', name='uix_1'),
  Index('bundle_data_hash_index', 'data_hash'),
  sqlite_autoincrement=True,
)

# Includes things like name, description, etc.
bundle_metadata = Table(
  'bundle_metadata',
  db_metadata,
  Column('id', Integer, primary_key=True, nullable=False),
  Column('bundle_uuid', String(63), ForeignKey(bundle.c.uuid), nullable=False),
  Column('metadata_key', String(63), nullable=False),
  Column('metadata_value', Text, nullable=False),
  Index('metadata_kv_index', 'metadata_key', 'metadata_value', mysql_length=63),
  sqlite_autoincrement=True,
)

# For each child_uuid, we have: key = child_path, target = (parent_uuid, parent_path)
bundle_dependency = Table(
  'bundle_dependency',
  db_metadata,
  Column('id', Integer, primary_key=True, nullable=False),
  Column('child_uuid', String(63), ForeignKey(bundle.c.uuid), nullable=False),
  Column('child_path', Text, nullable=False),
  # Deliberately omit ForeignKey(bundle.c.uuid), because bundles can have
  # dependencies to bundles not (yet) in the system.
  Column('parent_uuid', String(63), nullable=False),
  Column('parent_path', Text, nullable=False),
  sqlite_autoincrement=True,
)

# Stores actions sent from the client to the worker.
bundle_action = Table(
  'bundle_action',
  db_metadata,
  Column('id', Integer, primary_key=True, nullable=False),
  Column('bundle_uuid', String(63), ForeignKey(bundle.c.uuid), nullable=False),
  Column('action', Text, nullable=False),
  sqlite_autoincrement=True,
)

# The worksheet table does not have many columns now, but it will eventually
# include columns for owner, group, permissions, etc.
worksheet = Table(
  'worksheet',
  db_metadata,
  Column('id', Integer, primary_key=True, nullable=False),
  Column('uuid', String(63), nullable=False),
  Column('name', String(255), nullable=False),
  Column('owner_id', String(255), nullable=True),
  Column('title', String(255), nullable=True), # Short human-readable description of the worksheet
  Column('frozen', DateTime, nullable=True), # When the worksheet was frozen (forever immutable) if it is.
  UniqueConstraint('uuid', name='uix_1'),
  Index('worksheet_name_index', 'name'),
  Index('worksheet_owner_index', 'owner_id'),
  sqlite_autoincrement=True,
)

worksheet_item = Table(
  'worksheet_item',
  db_metadata,
  Column('id', Integer, primary_key=True, nullable=False),
  Column('worksheet_uuid', String(63), ForeignKey(worksheet.c.uuid), nullable=False),

  # A worksheet item is either:
  # - type = bundle (bundle_uuid != null)
  # - type = worksheet (subworksheet_uuid != null)
  # - type = markup (value != null)
  # - type = directive (value != null)
  # Deliberately omit ForeignKey(bundle.c.uuid), because worksheets can contain
  # bundles and worksheets not (yet) in the system.
  Column('bundle_uuid', String(63), nullable=True),
  Column('subworksheet_uuid', String(63), nullable=True),
  Column('value', Text, nullable=False),  # TODO: make this nullable
  Column('type', String(20), nullable=False),

  Column('sort_key', Integer, nullable=True),
  Index('worksheet_item_worksheet_uuid_index', 'worksheet_uuid'),
  Index('worksheet_item_bundle_uuid_index', 'bundle_uuid'),
  Index('worksheet_item_subworksheet_uuid_index', 'subworksheet_uuid'),
  sqlite_autoincrement=True,
)

# Worksheet tags
worksheet_tag = Table(
  'worksheet_tag',
  db_metadata,
  Column('id', Integer, primary_key=True, nullable=False),
  Column('worksheet_uuid', String(63), ForeignKey(worksheet.c.uuid), nullable=False),
  Column('tag', String(63), nullable=False),
  Index('worksheet_tag_worksheet_uuid_index', 'worksheet_uuid'),
  Index('worksheet_tag_tag_index', 'tag'),
  sqlite_autoincrement=True,
)

group = Table(
  'group',
  db_metadata,
  Column('id', Integer, primary_key=True, nullable=False),
  Column('uuid', String(63), nullable=False),
  Column('name', String(255), nullable=False),
  Column('user_defined', Boolean),
  Column('owner_id', String(255), nullable=True),
  UniqueConstraint('uuid', name='uix_1'),
  Index('group_name_index', 'name'),
  Index('group_owner_id_index', 'owner_id'),
  sqlite_autoincrement=True,
)

user_group = Table(
  'user_group',
  db_metadata,
  Column('id', Integer, primary_key=True, nullable=False),
  Column('group_uuid', String(63), ForeignKey(group.c.uuid), nullable=False),
  Column('user_id', String(63), nullable=False),
  # Whether a user is able to modify this group.
  Column('is_admin', Boolean),
  Index('group_uuid_index', 'group_uuid'),
  Index('user_id_index', 'user_id'),
  sqlite_autoincrement=True,
)

# Permissions for bundles
group_bundle_permission = Table(
  'group_bundle_permission',
  db_metadata,
  Column('id', Integer, primary_key=True, nullable=False),
  Column('group_uuid', String(63), ForeignKey(group.c.uuid), nullable=False),
  # Reference to a bundle
  Column('object_uuid', String(63), ForeignKey(bundle.c.uuid), nullable=False),
  # Permissions encoded as integer (see below)
  Column('permission', Integer, nullable=False),
  sqlite_autoincrement=True,
)

# Permissions for worksheets
group_object_permission = Table(
  'group_object_permission',
  db_metadata,
  Column('id', Integer, primary_key=True, nullable=False),
  Column('group_uuid', String(63), ForeignKey(group.c.uuid), nullable=False),
  # Reference to a worksheet object
  Column('object_uuid', String(63), ForeignKey(worksheet.c.uuid), nullable=False),
  # Permissions encoded as integer (see below)
  Column('permission', Integer, nullable=False),
  sqlite_autoincrement=True,
)

# A permission value is one of the following: none (0), read (1), or all (2).
GROUP_OBJECT_PERMISSION_NONE = 0x00
GROUP_OBJECT_PERMISSION_READ = 0x01
GROUP_OBJECT_PERMISSION_ALL = 0x02

# Keep track of events that happen.
event = Table(
  'event',
  db_metadata,
  Column('id', Integer, primary_key=True, nullable=False),
  Column('date', String(63), nullable=False),  # Deterministic function (e.g., 2015-09-11) of the start_time
  Column('start_time', DateTime, nullable=False),  # When did this event start?
  Column('end_time', DateTime, nullable=False),  # When did this event end?
  Column('duration', Float, nullable=False),  # How much time did this event take?
  Column('user_id', String(63), nullable=True),  # Who did it?
  Column('user_name', String(63), nullable=True),  # Who did it?
  Column('command', String(63), nullable=False),  # The command (gotten in bundle_rpc_server)
  Column('args', Text, nullable=False),  # JSON string
  Column('uuid', String(63), nullable=True),  # Either bundle or worksheet id (no ForeignKey because might not be in system anymore)
  # Indices
  Index('events_date_index', 'date'),
  Index('events_user_id_index', 'user_id'),
  Index('events_user_name_index', 'user_name'),
  Index('events_command_index', 'command'),
  Index('events_uuid_index', 'uuid'),
  sqlite_autoincrement=True,
)

# Store information about users.
user = Table(
  'user',
  db_metadata,
  Column('id', Integer, primary_key=True, nullable=False),

  # Basic information
  Column('user_id', String(63), nullable=False),
  Column('user_name', String(63), nullable=False),  # Mirrors the OAuth server (eventually move it here)

  # Quotas
  Column('time_quota', Float, nullable=False),  # Number of seconds allowed
  Column('time_used', Float, nullable=False),  # Number of seconds already used
  Column('disk_quota', Float, nullable=False),  # Number of bytes allowed
  Column('disk_used', Float, nullable=False),  # Number of bytes already used

  Index('user_user_id_index', 'user_id'),
  Index('user_user_name_index', 'user_name'),
  sqlite_autoincrement=True,
)
