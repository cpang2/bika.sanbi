# Imports
from Products.CMFCore.utils import getToolByName
from Products.CMFPlone.utils import _createObjectByType
from zope.interface import alsoProvides
from zope.schema import ValidationError
from DateTime import DateTime

from bika.lims.interfaces import IManagedStorage, IUnmanagedStorage
from bika.lims.utils import tmpID
from bika.lims.workflow import doActionFor
from bika.sanbi.interfaces import IBiospecimen, IAliquot
from project import ProjectView


def get_storage_objects(context, storage_uids):
    """Take a list of UIDs from the form, and resolve to a list of Storages.
    Accepts ManagedStorage, UnmanagedStorage, or StoragePosition UIDs.
    """
    uc = getToolByName(context, 'uid_catalog')
    bio_storages = []
    for uid in storage_uids:
        brain = uc(UID=uid)[0]
        instance = brain.getObject()
        if IUnmanagedStorage.providedBy(instance) \
                or len(instance.get_free_positions()) > 0:
            bio_storages.append(instance)

    return bio_storages


def count_storage_positions(storages):
    """"Return the number of items that can be stored in storages.
    This method is called in case all the storages are of type Managed.
    """
    count = 0
    for storage in storages:
        # If storage is a ManagedStorage, increment count for each
        # available StoragePosition
        if IManagedStorage.providedBy(storage):
            count += storage.getFreePositions()
        else:
            raise ValidationError("Storage %s is not a valid storage type" %
                                  storage)
    return count


def objects_between_two_uids(context, uid_1, uid_2, portal_type, wf_1, wf_2, state):
    """Retrieve the objects of type portal_type between two ordered objects
    using their uids.
    """
    w_tool = getToolByName(context, 'portal_workflow')
    uc = getToolByName(context, 'uid_catalog')
    first_id = uc(UID=uid_1)[0].id
    last_id = uc(UID=uid_2)[0].id
    objects = context.objectValues(portal_type)
    # Filter objects by workflow state active
    items = []
    for obj in objects:
        if IBiospecimen.providedBy(obj):
            st1 = w_tool.getStatusOf(wf_1, obj)
            st2 = w_tool.getStatusOf(wf_2, obj)
            if st1.get('review_state', None) == state and \
                            st2.get('cancellation_state', None) == 'active' and \
                                    first_id <= obj.getId() <= last_id:
                items.append(obj)

    return items


def assign_items_to_storages(context, items, storages):
    """ store items inside selected storages
    """
    wf = getToolByName(context, 'portal_workflow')
    for storage in storages:
        if IManagedStorage.providedBy(storage):
            free_positions = storage.get_free_positions()
            if len(items) <= len(free_positions):
                for i, item in enumerate(items):
                    item.setStorageLocation(free_positions[i])
                    wf.doActionFor(free_positions[i], 'occupy')
            else:
                for i, position in enumerate(free_positions):
                    items[i].setStorageLocation(position)
                    wf.doActionFor(position, 'occupy')
                items = items[len(free_positions):]
        elif IUnmanagedStorage.providedBy(storage):
            # Case of unmanaged storage there is no limit in storage until
            # user manually set the storage as full.
            for item in items:
                item.setStorageLocation(storage)


def create_sample(context, request, values, j, x):
    """Create sample as biospecimen or aliquot
    """
    # Retrieve the required tools
    uc = getToolByName(context, 'uid_catalog')
    # Determine if the sampling workflow is enabled
    workflow_enabled = context.bika_setup.getSamplingWorkflowEnabled()
    # Create sample or refer to existing for secondary analysis request
    sample = _createObjectByType('Sample', context, tmpID())
    # Update the created sample with indicated values
    sample.processForm(REQUEST=request, values=values)
    if 'datesampled' in values:
        sample.setDateSampled(values['datesampled'])
    else:
        sample.setDateSampled(DateTime())
    if 'datereceived' in values:
        sample.setDateReceived(values['datereceived'])
    else:
        sample.setDateReceived(DateTime())
    if 'datesampling' in values:
        sample.setSamplingDate(values['datesampling'])
    else:
        sample.setSamplingDate(DateTime())
    if 'datecreated' in values:
        field = sample.getField('DateCreated')
        field.set(sample, values['datecreated'])
    else:
        field = sample.getField('DateCreated')
        field.set(sample, DateTime())
    # Specifically set the storage location
    if 'StorageLocation' in values:
        sample.setStorageLocation(values['StorageLocation'])
    if 'kits' in values:
        field = sample.getField('Kit')
        field.set(sample, values['kits'][j].UID())
        alsoProvides(sample, IBiospecimen)
    if 'biospecimens' in values:
        field = sample.getField('LinkedSample')
        field.set(sample, values['biospecimens'][j].UID())
        # sample.setLinkedSample(values['biospecimens'][j].UID())
        alsoProvides(sample, IAliquot)
    context.manage_renameObject(sample.id, values['id_template'].format(id=x), )
    # Perform the appropriate workflow action
    workflow_action = 'sampling_workflow' if workflow_enabled \
        else 'no_sampling_workflow'
    doActionFor(sample, workflow_action)
    # Set the SampleID
    sample.edit(SampleID=sample.getId())
    # Return the newly created sample
    return sample

def create_samplepartition(context, data):
    """ Create partition object for sample(context)
    """
    partition = _createObjectByType('SamplePartition', context, data['part_id'])
    partition.unmarkCreationFlag()
    # Determine if the sampling workflow is enabled
    workflow_enabled = context.bika_setup.getSamplingWorkflowEnabled()
    # Perform the appropriate workflow action
    workflow_action = 'sampling_workflow' if workflow_enabled \
        else 'no_sampling_workflow'
    context.portal_workflow.doActionFor(partition, workflow_action)
    # Return the created partition
    return partition