
from xml.dom import minidom, Node, XML_NAMESPACE, XMLNS_NAMESPACE
import new
import re

import _base
from html5lib import constants, ihatexml
from html5lib.constants import namespaces

moduleCache = {}

def getDomModule(DomImplementation):
    name = "_" + DomImplementation.__name__+"builder"
    if name in moduleCache:
        return moduleCache[name]
    else:
        mod = new.module(name)
        objs = getDomBuilder(DomImplementation)
        mod.__dict__.update(objs)
        moduleCache[name] = mod    
        return mod

def getDomBuilder(DomImplementation):
    Dom = DomImplementation
    infoset_filter = ihatexml.InfosetFilter()
    class AttrList:
        def __init__(self, element):
            self.element = element
        def __iter__(self):
            return self.element.attributes.items().__iter__()
        def __setitem__(self, name, value):
            self.element.setAttribute(infoset_filter.coerceAttribute(name),
                                      infoset_filter.coerceCharacters(value))
        def items(self):
            return [(infoset_filter.fromXmlName(item[0]), item[1]) for item in
                     self.element.attributes.items()]
        def keys(self):
            return [infoset_filter.fromXmlName(item) for item in
                    self.element.attributes.keys()]
        def __getitem__(self, name):
            name = infoset_filter.toXmlName(name)
            return self.element.getAttribute(name)

        def __contains__(self, name):
            if isinstance(name, tuple):
                raise NotImplementedError
            else:
                return self.element.hasAttribute(infoset_filter.toXmlName(name))
    
    class NodeBuilder(_base.Node):
        def __init__(self, element):
            _base.Node.__init__(self, element.localName)
            self.element = element

        namespace = property(lambda self:hasattr(self.element, "namespaceURI")
                             and self.element.namespaceURI or None)

        def appendChild(self, node):
            node.parent = self
            self.element.appendChild(node.element)
    
        def insertText(self, data, insertBefore=None):
            data=infoset_filter.coerceCharacters(data)
            text = self.element.ownerDocument.createTextNode(data)
            if insertBefore:
                self.element.insertBefore(text, insertBefore.element)
            else:
                self.element.appendChild(text)
    
        def insertBefore(self, node, refNode):
            self.element.insertBefore(node.element, refNode.element)
            node.parent = self
    
        def removeChild(self, node):
            if node.element.parentNode == self.element:
                self.element.removeChild(node.element)
            node.parent = None
    
        def reparentChildren(self, newParent):
            while self.element.hasChildNodes():
                child = self.element.firstChild
                self.element.removeChild(child)
                newParent.element.appendChild(child)
            self.childNodes = []
    
        def getAttributes(self):
            return AttrList(self.element)
    
        def setAttributes(self, attributes):
            if attributes:
                for name, value in attributes.items():
                    if isinstance(name, tuple):
                        if name[0] is not None:
                            qualifiedName = (name[0] + ":" +
                                             infoset_filter.coerceAttribute(
                                name[1]))
                        else:
                            qualifiedName = infoset_filter.coerceAttribute(
                                name[1])
                        self.element.setAttributeNS(name[2], qualifiedName, 
                                                    value)
                    else:
                        self.element.setAttribute(
                            infoset_filter.coerceAttribute(name), value)
        attributes = property(getAttributes, setAttributes)
    
        def cloneNode(self):
            return NodeBuilder(self.element.cloneNode(False))
    
        def hasContent(self):
            return self.element.hasChildNodes()

        def getNameTuple(self):
            if self.namespace == None:
                return namespaces["html"], self.name
            else:
                return self.namespace, self.name

        nameTuple = property(getNameTuple)

    class TreeBuilder(_base.TreeBuilder):
        def documentClass(self):
            self.dom = Dom.getDOMImplementation().createDocument(None,None,None)
            return self
    
        def insertDoctype(self, token):
            name = token["name"]
            publicId = token["publicId"]
            systemId = token["systemId"]

            domimpl = Dom.getDOMImplementation()
            doctype = domimpl.createDocumentType(name, publicId, systemId)
            self.document.appendChild(NodeBuilder(doctype))
            if Dom == minidom:
                doctype.ownerDocument = self.dom
    
        def elementClass(self, name, namespace=None):
            if namespace is None and self.defaultNamespace is None:
                node = self.dom.createElement(name)
            else:
                node = self.dom.createElementNS(namespace, name)

            return NodeBuilder(node)
            
        def commentClass(self, data):
            return NodeBuilder(self.dom.createComment(data))
        
        def fragmentClass(self):
            return NodeBuilder(self.dom.createDocumentFragment())
    
        def appendChild(self, node):
            self.dom.appendChild(node.element)
    
        def testSerializer(self, element):
            return testSerializer(element)
    
        def getDocument(self):
            return self.dom
        
        def getFragment(self):
            return _base.TreeBuilder.getFragment(self).element
    
        def insertText(self, data, parent=None):
            data=infoset_filter.coerceCharacters(data)
            if parent <> self:
                _base.TreeBuilder.insertText(self, data, parent)
            else:
                # HACK: allow text nodes as children of the document node
                if hasattr(self.dom, '_child_node_types'):
                    if not Node.TEXT_NODE in self.dom._child_node_types:
                        self.dom._child_node_types=list(self.dom._child_node_types)
                        self.dom._child_node_types.append(Node.TEXT_NODE)
                self.dom.appendChild(self.dom.createTextNode(data))
    
        name = None
    
    def testSerializer(element):
        element.normalize()
        rv = []
        def serializeElement(element, indent=0):
            if element.nodeType == Node.DOCUMENT_TYPE_NODE:
                if element.name:
                    if element.publicId or element.systemId:
                        publicId = element.publicId or ""
                        systemId = element.systemId or ""
                        rv.append( """|%s<!DOCTYPE %s "%s" "%s">"""%(
                                ' '*indent, element.name, publicId, systemId))
                    else:
                        rv.append("|%s<!DOCTYPE %s>"%(' '*indent, element.name))
                else:
                    rv.append("|%s<!DOCTYPE >"%(' '*indent,))
            elif element.nodeType == Node.DOCUMENT_NODE:
                rv.append("#document")
            elif element.nodeType == Node.DOCUMENT_FRAGMENT_NODE:
                rv.append("#document-fragment")
            elif element.nodeType == Node.COMMENT_NODE:
                rv.append("|%s<!-- %s -->"%(' '*indent, element.nodeValue))
            elif element.nodeType == Node.TEXT_NODE:
                rv.append("|%s\"%s\"" %(' '*indent, element.nodeValue))
            else:
                if (hasattr(element, "namespaceURI") and
                    element.namespaceURI not in (None,
                                              constants.namespaces["html"])):
                    name = "%s %s"%(constants.prefixes[element.namespaceURI],
                                    element.nodeName)
                else:
                    name = element.nodeName
                rv.append("|%s<%s>"%(' '*indent, name))
                if element.hasAttributes():
                    i = 0
                    attr = element.attributes.item(i)
                    while attr:
                        name = infoset_filter.fromXmlName(attr.localName)
                        value = attr.value
                        ns = attr.namespaceURI
                        if ns:
                            name = "%s %s"%(constants.prefixes[ns], name)
                        i += 1
                        attr = element.attributes.item(i)

                        rv.append('|%s%s="%s"' % (' '*(indent+2), name, value))
            indent += 2
            for child in element.childNodes:
                serializeElement(child, indent)
        serializeElement(element, 0)
    
        return "\n".join(rv)
    
    def dom2sax(node, handler, nsmap={'xml':XML_NAMESPACE}):
      if node.nodeType == Node.ELEMENT_NODE:
        if not nsmap:
          handler.startElement(node.nodeName, node.attributes)
          for child in node.childNodes: dom2sax(child, handler, nsmap)
          handler.endElement(node.nodeName)
        else:
          attributes = dict(node.attributes.itemsNS()) 
    
          # gather namespace declarations
          prefixes = []
          for attrname in node.attributes.keys():
            attr = node.getAttributeNode(attrname)
            if (attr.namespaceURI == XMLNS_NAMESPACE or
               (attr.namespaceURI == None and attr.nodeName.startswith('xmlns'))):
              prefix = (attr.localName != 'xmlns' and attr.localName or None)
              handler.startPrefixMapping(prefix, attr.nodeValue)
              prefixes.append(prefix)
              nsmap = nsmap.copy()
              nsmap[prefix] = attr.nodeValue
              del attributes[(attr.namespaceURI, attr.localName)]
    
          # apply namespace declarations
          for attrname in node.attributes.keys():
            attr = node.getAttributeNode(attrname)
            if attr.namespaceURI == None and ':' in attr.nodeName:
              prefix = attr.nodeName.split(':')[0]
              if nsmap.has_key(prefix):
                del attributes[(attr.namespaceURI, attr.localName)]
                attributes[(nsmap[prefix],attr.localName)]=attr.nodeValue
    
          # SAX events
          ns = node.namespaceURI or nsmap.get(None,None)
          handler.startElementNS((ns,node.nodeName), node.nodeName, attributes)
          for child in node.childNodes: dom2sax(child, handler, nsmap)
          handler.endElementNS((ns, node.nodeName), node.nodeName)
          for prefix in prefixes: handler.endPrefixMapping(prefix)
    
      elif node.nodeType in [Node.TEXT_NODE, Node.CDATA_SECTION_NODE]:
        handler.characters(node.nodeValue)
    
      elif node.nodeType == Node.DOCUMENT_NODE:
        handler.startDocument()
        for child in node.childNodes: dom2sax(child, handler, nsmap)
        handler.endDocument()
    
      elif node.nodeType == Node.DOCUMENT_FRAGMENT_NODE:
        for child in node.childNodes: dom2sax(child, handler, nsmap)
    
      else:
        # ATTRIBUTE_NODE
        # ENTITY_NODE
        # PROCESSING_INSTRUCTION_NODE
        # COMMENT_NODE
        # DOCUMENT_TYPE_NODE
        # NOTATION_NODE
        pass
        
    return locals()

# Keep backwards compatibility with things that directly load 
# classes/functions from this module
for key, value in getDomModule(minidom).__dict__.items():
	globals()[key] = value
