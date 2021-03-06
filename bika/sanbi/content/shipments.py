from Products.ATContentTypes.content import schemata
from Products.Archetypes import atapi
from bika.sanbi.config import PROJECTNAME
from plone.app.folder.folder import ATFolder, ATFolderSchema
from zope.interface.declarations import implements
from bika.sanbi.interfaces import IShipments

schema = ATFolderSchema.copy()


class Shipments(ATFolder):
    implements(IShipments)
    displayContentsTab = False
    schema = schema

schemata.finalizeATCTSchema(schema, folderish=True, moveDiscussion=False)
atapi.registerType(Shipments, PROJECTNAME)
