'''
Worksheet is the ORM class for a worksheet in the bundle system. This class is
backed by two tables in the database: worksheet and worksheet_item.

A single worksheet will have many item rows, ordered by the id the database
assigned to each one. Each of this rows will have a string value and and
optionally a bundle_uuid which makes it a bundle rows.
'''
from codalab.common import precondition
from codalab.lib import spec_util
from codalab.model.orm_object import ORMObject


# We will keep worksheet items sorted in the database by maintining a sort_key
# for each item that was batch-added to a worksheet by a call to update_worksheet_items.
# These sort keys will be strictly upper-bounded by the maximum id at the time
# at which the edit was BEGUN. This ensures that any worksheet items appended to
# the sheet between the time the edit was begun and committed will have ids
# greater than the maximum sort key.
def item_sort_key(item):
    return item['id'] if item['sort_key'] is None else item['sort_key']

class Worksheet(ORMObject):
    COLUMNS = ('uuid', 'name', 'owner_id', 'title', 'frozen')

    def validate(self):
        '''
        Check a number of basic conditions that would indicate serious errors if
        they do not hold. Right now, validation only checks this worksheet's uuid
        and its name.
        '''
        spec_util.check_uuid(self.uuid)
        spec_util.check_name(self.name)

    def __repr__(self):
        return 'Worksheet(uuid=%r, name=%r)' % (self.uuid, self.name)

    def simple_str(self):
        return '%s(%s)' % (self.name, self.uuid)

    def update_in_memory(self, row, strict=False):
        items = row.pop('items', None)
        self.tags = row.pop('tags', None)
        if not row.get('uuid'):
            row['uuid'] = spec_util.generate_uuid()
        super(Worksheet, self).update_in_memory(row)
        if items is not None:
            self.items = [(item['bundle_uuid'], item['subworksheet_uuid'], item['value'], item['type']) for item in items]
            self.last_item_id = max(item['id'] for item in items) if items else -1
        else:
            self.items = None
            self.last_item_id = None

    def to_dict(self):
        result = super(Worksheet, self).to_dict()
        result['tags'] = self.tags
        result['items'] = self.items
        result['last_item_id'] = self.last_item_id
        return result
