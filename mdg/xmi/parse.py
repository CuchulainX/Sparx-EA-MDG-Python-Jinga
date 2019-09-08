import os
import re
import yaml

from mdg.uml import UMLPackage, UMLAssociation, UMLInstance, UMLEnumeration, UMLClass, UMLAttribute

ns = {
    'uml': 'http://schema.omg.org/spec/UML/2.1',
    'xmi': 'http://schema.omg.org/spec/XMI/2.1',
    'thecustomprofile': 'http://www.sparxsystems.com/profiles/thecustomprofile/1.0',
    'NIEM_PSM_profile': 'http://www.omg.org/spec/NIEM-UML/20130801/NIEM_PSM_Profile',
}

settings = None


def parse_uml(element, root):
    """ Root package parser entry point.
    """
    global settings
    test_package = None

    with open(os.environ.get('PYXMI_SETTINGS_MODULE'), 'r') as config_file:
        settings = yaml.load(config_file.read(), Loader=yaml.SafeLoader)

    # Find the element that is the root for models
    print("Parsing models")
    model_element = element.xpath("//packagedElement[@name='%s']" % settings['model_package'], namespaces=ns)
    if len(model_element) == 0:
        raise ValueError("Model packaged element not found. Settings has:{}".format(settings['model_package']))
    model_element = model_element[0]

    # Create our root model UMLPackage and parse in 3 passes
    e_type = model_element.get('{%s}type' % ns['xmi'])
    if e_type == 'uml:Package':
        model_package = package_parse(model_element, root)
        package_parse_inheritance(model_package)
        package_parse_associations(model_package, model_element, model_element)
    else:
        raise ValueError('Error - Non uml:Package element provided to packagedElement parser')

    # Find the element that is the root for test data
    print("Parsing test cases")
    test_element = element.xpath("//packagedElement[@name='%s']" % settings['test_package'], namespaces=ns)
    if len(test_element) == 0:
        raise ValueError("Test packaged element not found. Settings has:{}".format(settings['test_package']))
    test_element = test_element[0]

    # Create our root test data UMLPackage and parse in 2 passes. Does not support inheritance
    e_type = test_element.get('{%s}type' % ns['xmi'])
    if e_type == 'uml:Package':
        test_package = package_parse(test_element, root)
        package_parse_associations(test_package, test_element, test_element)

    # With our test package parsed, we must return a list of instances instead of hierarchy of packages
    test_cases = parse_test_cases(test_package)
    return model_package, test_cases


def parse_test_cases(package):
    """ Looks through package hierarchy for instances with request or response stereotype
    and returns list of instances.
    :rtype: list<UMLInstance>
    """
    test_cases = []

    # for instance in package.instances:
    #     if instance.stereotype in ['request', 'response']:
    #         test_cases.append(instance)
    #
    # for child in package.children:
    #     res = parse_test_cases(child)
    #     if res:
    #         test_cases += res

    return test_cases


def package_parse(element, root):
    """ Extract package details, call class parser for classes and self parser for sub-packages.
    Associations are not done here, but in a 2nd pass using the parse_associations function.
    :param element:
    :param root:
    :return:
    :rtype: UMLPackage
    """
    name = element.get('name')
    id = element.get('{%s}id' % ns['xmi'])

    package = UMLPackage(id, name)
    package.element = element
    package.root_element = root

    # Detail is Sparx specific
    # TODO: Put modelling tool in settings and use tool specific parser here
    detail = root.xpath("//element[@xmi:idref='%s']" % package.id, namespaces=ns)[0]
    properties = detail.find('properties')
    package.stereotype = properties.get('stereotype')
    if package.stereotype is not None:
        package.inherited_stereotypes.append([package.stereotype, package])

    # Loop through all child elements and get classes and sub packages
    for child in element:
        e_type = child.get('{%s}type' % ns['xmi'])

        if e_type == 'uml:Package':
            pkg = package_parse(child, root)
            package.children.append(pkg)

        elif e_type == 'uml:Class':
            cls = class_parse(package, child, root)
            if cls.name is not None:
                package.classes.append(cls)

        elif e_type == 'uml:InstanceSpecification':
            ins = instance_parse(package, child, root)
            if ins.name is not None:
                package.instances.append(ins)

        elif e_type == 'uml:Enumeration':
            enumeration = enumeration_parse(package, child)
            if enumeration.name is not None:
                package.enumerations.append(enumeration)

    return package


def package_parse_associations(package, element, root_element):
    """ Packages and classes should already have been parsed so now we link classes for each association.
    This gets messy as XMI output varies based on association type.
    This supports both un-specified and source to destination directional associations
    :param root_element:
    :param element: XML Element
    :type package: UMLPackage
    """
    for child in element:
        e_type = child.get('{%s}type' % ns['xmi'])
        e_id = child.get('{%s}id' % ns['xmi'])

        if e_type == 'uml:Association':
            assoc_source_id = None
            assoc_dest_id = None
            assoc_source_elem = None
            assoc_dest_elem = None

            for assoc in child:
                # If unspecified direction then both source and destination info are child elements within the
                # association
                assoc_type = assoc.get('{%s}type' % ns['xmi'])
                assoc_id = assoc.get('{%s}id' % ns['xmi'])
                if assoc_id is not None and assoc_type == 'uml:Property' and assoc_id[:8] == 'EAID_src':
                    assoc_source_elem = assoc
                    assoc_source_type_elem = assoc.find('type')
                    assoc_source_id = assoc_source_type_elem.get('{%s}idref' % ns['xmi'])
                if assoc_id is not None and assoc_type == 'uml:Property' and assoc_id[:8] == 'EAID_dst':
                    assoc_dest_elem = assoc
                    assoc_dest_type_elem = assoc.find('type')
                    assoc_dest_id = assoc_dest_type_elem.get('{%s}idref' % ns['xmi'])

            # If association direction is source to destination then
            # destination class info is found as an ownedAttribute in the source element
            if assoc_dest_id is None:
                for assoc in child:
                    if assoc.tag == 'memberEnd':
                        assoc_idref = assoc.get('{%s}idref' % ns['xmi'])
                        if assoc_idref[:8] == 'EAID_dst':
                            try:
                                assoc_dest_elem = \
                                    root_element.xpath("//ownedAttribute[@xmi:id='%s']" % assoc_idref,
                                                       namespaces=ns)[0]
                            except IndexError as e:
                                print("Failed to find member end association destination. Id: {}".format(assoc_idref))
                                raise e
                            assoc_dest_type_elem = assoc_dest_elem.find('type')
                            assoc_dest_id = assoc_dest_type_elem.get('{%s}idref' % ns['xmi'])

            # print("association: src id={} dest id={}".format(assoc_source_id,assoc_dest_id))
            # TODO: Raise error if we don't have a source and dest
            source = package.root_package.find_by_id(assoc_source_id)
            dest = package.root_package.find_by_id(assoc_dest_id)
            if source is not None \
                    and dest is not None \
                    and assoc_source_elem is not None \
                    and assoc_dest_elem is not None:
                association = association_parse(package, assoc_source_elem, assoc_dest_elem, source, dest)
                package.associations.append(association)
            else:
                print("Unable to create association id={}".format(e_id))

    for package_child in package.children:
        element = element.xpath("//packagedElement[@xmi:id='%s']" % package_child.id, namespaces=ns)[0]
        package_parse_associations(package_child, element, root_element)


def package_parse_inheritance(package):
    """ Looks for classes with a supertype and finds the correct object """
    for cls in package.classes:
        if cls.supertype_id is not None:
            cls.supertype = package.root_package.find_by_id(cls.supertype_id)
            cls.supertype.is_supertype = True
            if cls.id_attribute is None:
                cls.id_attribute = cls.supertype.id_attribute

        for attr in cls.attributes:
            if attr.classification_id is not None:
                attr.classification = package.root_package.find_by_id(attr.classification_id)

    for child in package.children:
        package_parse_inheritance(child)


def instance_parse(package, element, root):
    ins = UMLInstance(package, element.get('name'), element.get('{%s}id' % ns['xmi']))

    # Detail is sparx specific
    # TODO: Put modelling tool in settings and use tool specific parser here
    detail = root.xpath("//element[@xmi:idref='%s']" % ins.id, namespaces=ns)[0]
    properties = detail.find('properties')
    ins.stereotype = properties.get('stereotype')

    # Create attributes for each item found in the run_state
    # TODO: Change this to using an re
    extended_properties = detail.find('extended_properties')
    if extended_properties.get('run_state') is not None:
        run_state = extended_properties.get('run_state')
        vars = run_state.split('@ENDVAR;')
        for var in vars:
            if var != '':
                variable, value = (var.split(';')[1:3])
                attr = UMLAttribute(ins, variable.split('=')[1], value.split('=')[1])
                ins.attributes.append(attr)
    return ins


def association_parse(package, source_element, dest_element, source, dest):
    association = UMLAssociation(package, source, dest)

    # Extract multiplicity for source
    source_lower = source_element.find('lowerValue')
    if source_lower is not None:
        source_lower = source_lower.get('value')
        if source_lower == '-1':
            source_lower = '*'
        source_upper = source_element.find('upperValue').get('value')
        if source_upper == '-1':
            source_upper = '*'
        association.source_multiplicity = (source_lower, source_upper)

    # Extract multiplicity for dest
    dest_lower = dest_element.find('lowerValue')
    if dest_lower is not None:
        dest_lower = dest_lower.get('value')
        if dest_lower == '-1':
            dest_lower = '*'
        dest_upper = dest_element.find('upperValue').get('value')
        if dest_upper == '-1':
            dest_upper = '*'
        association.dest_multiplicity = (dest_lower, dest_upper)

    # print( '{}:{} to {}:{}'.format(self.source.name, self.source_multiplicity, self.dest.name,
    # self.dest_multiplicity))

    # Use multiplicities to calculate the type of association
    if association.source_multiplicity[1] == '*' and association.dest_multiplicity[1] in ('0', '1'):
        association.association_type = 'ManyToOne'
    elif association.dest_multiplicity[1] == '*' and association.source_multiplicity[1] in ('0', '1'):
        association.association_type = 'OneToMany'
    elif association.dest_multiplicity[1] == '*' and association.source_multiplicity[1] == '*':
        association.association_type = 'ManyToMany'
    elif association.dest_multiplicity[1] in ('0', '1') and association.source_multiplicity[1] in ('0', '1'):
        association.association_type = 'OneToOne'

    # If it's an association to or from a multiple then pluralize the name
    # TODO: Allow pluralized name to be specified in UML
    if dest_element.get('name') is not None:
        association.dest_name = dest_element.get('name')
    else:
        # Use opposing ends class name as attribute name for association
        association.dest_name = association.source.name.lower()
        if association.source_multiplicity[1] == '*':
            association.dest_name += 's'

    if source_element.get('name') is not None:
        association.source_name = source_element.get('name')
    else:
        # Use opposing ends class name as attribute name for association
        association.source_name = association.destination.name.lower()
        if association.dest_multiplicity[1] == '*':
            association.source_name += 's'

    # print('Assoc in {}: {} to {}: type = {}'.format(self.source.name, self.source_name, self.dest_name,
    # self.association_type) )
    return association


def enumeration_parse(package, element):
    enumeration = UMLEnumeration(package, element.get('name'), element.get('{%s}id' % ns['xmi']))

    # Loop through class elements children for values.
    for child in element:
        e_type = child.get('{%s}type' % ns['xmi'])
        if e_type == 'uml:EnumerationLiteral':
            enumeration.values.append(child.get('name'))
    return enumeration


def class_parse(package, element, root):
    cls = UMLClass(package, element.get('name'), element.get('{%s}id' % ns['xmi']))
    if element.get('isAbstract') == 'true':
        cls.is_abstract = True
    else:
        cls.is_abstract = False

    # If the class is inherited from a superclass then get the ID. The actual object will be found in a separate pass
    # as it may not have been parsed yet
    supertype_element = element.find('generalization')
    if supertype_element is not None:
        cls.supertype_id = supertype_element.get('general')

    # Loop through class elements children for attributes.
    for child in element:
        e_type = child.get('{%s}type' % ns['xmi'])

        if e_type == 'uml:Property':
            # Associations will be done in a separate pass
            if child.get('association') is None and child.get('name') is not None:
                attr = attr_parse(cls, child, root)
                cls.attributes.append(attr)

    # Detail is sparx sprecific
    # TODO: Put modelling tool in settings and use tool specific parser here
    detail = root.xpath("//element[@xmi:idref='%s']" % cls.id, namespaces=ns)[0]

    # Get stereotypes, when multiple are provided only the first is found in the stereotype tag but all are found in
    # xrefs
    xrefs = detail.find('xrefs')
    value = xrefs.get('value')
    if value is not None:
        cls.stereotypes = re.findall('@STEREO;Name=(.*?);', value)

    return cls


def attr_parse(parent, element, root):
    global settings
    attr = UMLAttribute(parent, element.get('name'), element.get('{%s}id' % ns['xmi']))

    attr.visibility = element.get('visibility')
    type_elem = element.find('type')
    type_id = type_elem.get('{%s}idref' % ns['xmi'])
    if type_id[:4] == 'EAID':
        attr.classification_id = type_id

    # Detail is sparx sprecific
    # TODO: Put modelling tool in settings and use tool specific parser here
    detail = root.xpath("//attribute[@xmi:idref='%s']" % attr.id, namespaces=ns)[0]
    properties = detail.find('properties')
    attr.type = properties.get('type')

    if properties.get('type') in settings['types'].keys():
        attr.dest_type = settings['types'][properties.get('type')]
    else:
        attr.dest_type = properties.get('type')

    xrefs = detail.find('xrefs')
    if xrefs.get('value') is not None and 'NAME=isID' in xrefs.get('value'):
        attr.is_id = True
        attr.parent.id_attribute = attr
    else:
        attr.is_id = False

    # Todo: decide how to include string lengths in UML
    if attr.type == 'string':
        attr.length = 100

    stereotype = detail.find('stereotype')
    if stereotype is not None:
        attr.stereotype = stereotype.get('stereotype')

    constraints = detail.find('Constraints')
    if constraints is not None:
        for constraint in constraints:
            name = constraint.get('name')
            if name == 'unique':
                attr.is_unique = True
            elif name.startswith('length'):
                attr.length = int(name.split("=")[1])

    return attr