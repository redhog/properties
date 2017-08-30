"""containers.py: List/Set/Tuple properties"""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

from warnings import warn

from six import integer_types, iteritems, PY2

from .base import HasProperties
from .instance import Instance
from .. import basic
from .. import utils

if PY2:
    from types import ClassType                                                #pylint: disable=no-name-in-module
    CLASS_TYPES = (type, ClassType)
else:
    CLASS_TYPES = (type,)


def add_properties_callbacks(cls):
    """Class decorator to add change notifications to builtin containers"""
    for name in cls._mutators:                                                 #pylint: disable=protected-access
        if not hasattr(cls, name):
            continue
        setattr(cls, name, properties_mutator(cls, name))
    for name in cls._operators:                                                #pylint: disable=protected-access
        if not hasattr(cls, name):
            continue
        setattr(cls, name, properties_operator(cls, name))
    for name in cls._ioperators:                                               #pylint: disable=protected-access
        if not hasattr(cls, name):
            continue
        setattr(cls, name, properties_mutator(cls, name, True))
    return cls


def properties_mutator(cls, name, ioper=False):
    """Wraps a mutating container method to add HasProperties notifications

    If the container is not part of a HasProperties instance, behavior
    is unchanged. However, if it is part of a HasProperties instance
    the new method calls set, triggering change notifications.
    """

    def wrapper(self, *args, **kwargs):
        """Mutate if not part of HasProperties; copy/modify/set otherwise"""
        if (
                getattr(self, '_instance', None) is None or
                getattr(self, '_name', '') == '' or
                self is not getattr(self._instance, self._name)
        ):
            return getattr(super(cls, self), name)(*args, **kwargs)
        else:
            copy = cls(self)
            val = getattr(copy, name)(*args, **kwargs)
            if not ioper:
                setattr(self._instance, self._name, copy)
            self._instance = None
            self._name = ''
            return val

    wrapped = getattr(cls, name)
    wrapper.__name__ = wrapped.__name__
    wrapper.__doc__ = wrapped.__doc__
    return wrapper


def properties_operator(cls, name):
    """Wraps a container operator to ensure container class is maintained"""

    def wrapper(self, *args, **kwargs):
        """Perform operation and cast to container class"""
        output = getattr(super(cls, self), name)(*args, **kwargs)
        return cls(output)

    wrapped = getattr(cls, name)
    wrapper.__name__ = wrapped.__name__
    wrapper.__doc__ = wrapped.__doc__
    return wrapper


@add_properties_callbacks
class PropertiesList(list):
    """List for :class:`List <properties.List>` Property with notifications

    This class keeps track of the Property and HasProperties
    instance it is held by. When the list is modified, it is set again
    rather than mutating. This decreases performance but allows notifications
    to fire on the HasProperties instance.

    If a **PropertiesList** is not part of a HasProperties
    class, its behavior is identical to a built-in :code:`list`.
    """

    _mutators = ['append', 'extend', 'insert', 'pop', 'remove', 'clear',
                 'sort', 'reverse', '__setitem__', '__delitem__',
                 '__delslice__', '__setslice__']
    _operators = ['__add__', '__mul__', '__rmul__']
    _ioperators = ['__iadd__', '__imul__']


@add_properties_callbacks
class PropertiesSet(set):
    """Set for :class:`Set <properties.Set>` Property with notifications

    This class keeps track of the Property and HasProperties
    instance it is held by. When the set is modified, it is set again
    rather than mutating. This decreases performance but allows notifications
    to fire on the HasProperties instance.

    If a **PropertiesSet** is not part of a HasProperties
    class, its behavior is identical to a built-in :code:`set`.
    """

    _mutators = ['add', 'clear', 'difference_update', 'discard',
                 'intersection_update', 'pop', 'remove',
                 'symmetric_difference_update', 'update']
    _operators = ['__and__', '__or__', '__sub__', '__xor__',
                  '__rand__', '__ror__', '__rsub__', '__rxor__', 'copy',
                  'difference', 'intersection', 'symmetric_difference',
                  'union']
    _ioperators = ['__iand__', '__ior__', '__isub__', '__ixor__']


@add_properties_callbacks
class PropertiesDict(dict):

    _mutators = ['clear', 'pop', 'popitem', 'setdefault', 'update',
                 '__delitem__', '__setitem__']
    _operators = ['copy', 'fromkeys']
    _ioperators = []

OBSERVABLE = {
    list: PropertiesList,
    set: PropertiesSet,
    dict: PropertiesDict,
}

def validate_prop(value):
    """Validate Property instance for container items"""
    if (
            isinstance(value, CLASS_TYPES) and
            issubclass(value, HasProperties)
    ):
        value = Instance('', value)
    if not isinstance(value, basic.Property):
        raise TypeError('Contained prop must be a Property instance or '
                        'HasProperties class')
    if value.default is not utils.undefined:
        warn('Contained prop default ignored: {}'.format(value.default),
             RuntimeWarning)
    return value


class Tuple(basic.Property):
    """Property for tuples, where each entry is another Property type

    **Available keywords** (in addition to those inherited from
    :ref:`Property <property>`):

    * **prop** - Property instance that specifies the Property type of
      each entry in the **Tuple**. A HasProperties class may also be
      specified; this is simply coerced to an
      :ref:`Instance Property <instance>` of that class.
    * **min_length** - Minimum valid length of the tuple, inclusive. If None
      (the default), there is no minimum length.
    * **max_length** - Maximum valid length of the tuple, inclusive. If None
      (the default), there is no maximum length.
    * **coerce** - If False, input must be a tuple. If True, container
      types are coerced to a tuple and other non-container values become a
      length-1 tuple. Default value is False.
    """

    class_info = 'a tuple'
    _class_default = tuple

    def __init__(self, doc, prop, **kwargs):
        self.prop = prop
        super(Tuple, self).__init__(doc, **kwargs)

    @property
    def prop(self):
        """Property instance or HasProperties class allowed in the list"""
        return self._prop

    @prop.setter
    def prop(self, value):
        self._prop = validate_prop(value)

    @property
    def name(self):
        """The name of the property on a HasProperties class

        This is set in the metaclass. For tuples, prop inherits the name
        """
        return getattr(self, '_name', '')

    @name.setter
    def name(self, value):
        self.prop.name = value
        self._name = value

    @property
    def min_length(self):
        """Minimum allowed length of the tuple"""
        return getattr(self, '_min_length', None)

    @min_length.setter
    def min_length(self, value):
        if not isinstance(value, integer_types) or value < 0:
            raise TypeError('min_length must be integer >= 0')
        if self.max_length is not None and value > self.max_length:
            raise TypeError('min_length must be <= max_length')
        self._min_length = value

    @property
    def max_length(self):
        """Maximum allowed length of the tuple"""
        return getattr(self, '_max_length', None)

    @max_length.setter
    def max_length(self, value):
        if not isinstance(value, integer_types) or value < 0:
            raise TypeError('max_length must be integer >= 0')
        if self.min_length is not None and value < self.min_length:
            raise TypeError('max_length must be >= min_length')
        self._max_length = value

    @property
    def coerce(self):
        """Coerce sets/lists to tuples or other inputs to length-1 tuples"""
        return getattr(self, '_coerce', False)

    @coerce.setter
    def coerce(self, value):
        if not isinstance(value, bool):
            raise TypeError('coerce must be a boolean')
        self._coerce = value

    @property
    def info(self):
        """Supplemental description of the list, with length and type"""
        itext = self.class_info
        if self.prop.info:
            itext += ' (each item is {})'.format(self.prop.info)
        if self.max_length is None and self.min_length is None:
            return itext
        if self.max_length is None:
            lentext = 'length >= {}'.format(self.min_length)
        elif self.max_length == self.min_length:
            lentext = 'length of {}'.format(self.min_length)
        else:
            lentext = 'length between {mn} and {mx}'.format(
                mn='0' if self.min_length is None else self.min_length,
                mx=self.max_length,
            )
        return '{} with {}'.format(itext, lentext)

    def validate(self, instance, value):
        """Check the class of the container and validate each element

        This returns a copy of the container to prevent unwanted sharing of
        pointers.
        """
        if not self.coerce and not isinstance(value, self._class_default):
            self.error(instance, value)
        if self.coerce and not isinstance(value, (list, tuple, set)):
            value = [value]
        out = []
        for val in value:
            try:
                out += [self.prop.validate(instance, val)]
            except ValueError:
                self.error(instance, val, extra='This item is invalid.')
        return self._class_default(out)

    def assert_valid(self, instance, value=None):
        """Check if tuple and contained properties are valid"""
        valid = super(Tuple, self).assert_valid(instance, value)
        if not valid:
            return False
        if value is None:
            value = instance._get(self.name)
        if value is None:
            return True
        if self.min_length is not None and len(value) < self.min_length:
            self.error(instance, value)
        if self.max_length is not None and len(value) > self.max_length:
            self.error(instance, value)
        for val in value:
            self.prop.assert_valid(instance, val)
        return True

    def serialize(self, value, **kwargs):
        """Return a serialized copy of the tuple"""
        kwargs.update({'include_class': kwargs.get('include_class', True)})
        if self.serializer is not None:
            return self.serializer(value, **kwargs)
        if value is None:
            return None
        serial_list = [self.prop.serialize(val, **kwargs)
                       for val in value]
        return serial_list

    def deserialize(self, value, **kwargs):
        """Return a deserialized copy of the tuple"""
        kwargs.update({'trusted': kwargs.get('trusted', False)})
        if self.deserializer is not None:
            return self.deserializer(value, **kwargs)
        if value is None:
            return None
        output_list = [self.prop.deserialize(val, **kwargs)
                       for val in value]
        return self._class_default(output_list)

    def equal(self, value_a, value_b):
        try:
            if len(value_a) == len(value_b):
                equal_list = [self.prop.equal(a, b)
                              for a, b in zip(value_a, value_b)]
                return all(equal_list)
        except TypeError:
            pass
        return False

    @staticmethod
    def to_json(value, **kwargs):
        """Return a copy of the tuple as a list

        If the tuple contains HasProperties instances, they are serialized.
        """
        serial_list = [
            val.serialize(**kwargs) if isinstance(val, HasProperties)
            else val for val in value
        ]
        return serial_list

    @staticmethod
    def from_json(value, **kwargs):
        """Return a copy of the json tuple

        Individual list elements cannot be converted statically since the
        tuple's prop type is unknown.
        """
        return tuple(value)

    def sphinx_class(self):
        """Redefine sphinx class to point to prop class"""
        classdoc = self.prop.sphinx_class().replace(
            ':class:`', '{info} of :class:`'
        )
        return classdoc.format(info=self.class_info)


class List(Tuple):
    """Property for lists, where each entry is another Property type

    **Available keywords** (in addition to those inherited from
    :ref:`Property <property>`):

    * **prop** - Property instance that specifies the Property type of
      each entry in the **List**. A HasProperties class may also be specified;
      this is simply coerced to an
      :ref:`Instance Property <instance>` of that class.
    * **min_length** - Minimum valid length of the list, inclusive. If None
      (the default), there is no minimum length.
    * **max_length** - Maximum valid length of the list, inclusive. If None
      (the default), there is no maximum length.
    * **coerce** - If False, input must be a list. If True, container
      types are coerced to a list and other non-container values become a
      length-1 list. Default value is False.
    * **observe_mutations** - If False, the underlying storage class is
      a built-in :code:`list`. If True, the underlying storage class will be
      :class:`PropertiesList <properties.base.containers.PropertiesList>`.
      The benefit of PropertiesList is that all mutations
      will trigger HasProperties change notifications. The drawback is
      slower performance as copies of the list are made on every operation.
    """

    class_info = 'a list'
    _class_default = list

    @property
    def observe_mutations(self):
        """observe_mutations makes all mutations fire change notifications"""
        return getattr(self, '_observe_mutations', False)

    @observe_mutations.setter
    def observe_mutations(self, value):
        if not isinstance(value, bool):
            raise TypeError('observe_mutations must be a boolean')
        self._observe_mutations = value

    def validate(self, instance, value):
        value = super(List, self).validate(instance, value)
        if not self.observe_mutations:
            return value
        value = OBSERVABLE[self._class_default](value)
        value._name = self.name
        value._instance = instance
        return value

    @staticmethod
    def from_json(value, **kwargs):
        """Return a copy of the json list as a list

        Individual list elements cannot be converted statically since the
        list's prop type is unknown.
        """
        return list(value)


class Set(List):
    """Property for sets, where each entry is another Property type

    **Available keywords** (in addition to those inherited from
    :ref:`Property <property>`):

    * **prop** - Property instance that specifies the Property type of
      each entry in the **Set**. A HasProperties class may also be specified;
      this is simply coerced to an
      :ref:`Instance Property <instance>` of that class.
    * **min_length** - Minimum valid length of the set, inclusive. If None
      (the default), there is no minimum length.
    * **max_length** - Maximum valid length of the set, inclusive. If None
      (the default), there is no maximum length.
    * **coerce** - If False, input must be a set. If True, container
      types are coerced to a set and other non-container values become a
      length-1 set. Default value is False.
    * **observe_mutations** - If False, the underlying storage class is
      a built-in :code:`set`. If True, the underlying storage class will be
      :class:`PropertiesSet <properties.base.containers.PropertiesSet>`.
      The benefit of PropertiesSet is that all mutations
      will trigger HasProperties change notifications. The drawback is
      slower performance as copies of the set are made on every operation.
    """

    class_info = 'a set'
    _class_default = set

    def equal(self, value_a, value_b):
        try:
            if len(value_a) != len(value_b):
                return False
            copy_b = value_b.copy()
            for item_a in value_a:
                for item_b in copy_b:
                    if self.prop.equal(item_a, item_b):
                        copy_b.remove(item_b)
                        break
            return len(copy_b) == 0
        except (TypeError, AttributeError):
            return False

    @staticmethod
    def from_json(value, **kwargs):
        """Return a copy of the json list as a set

        Individual set elements cannot be converted statically since the
        set's prop type is unknown.
        """
        return set(value)


class Dict(basic.Property):

    class_info = 'a dictionary'
    _class_default = dict

    @property
    def observe_mutations(self):
        """observe_mutations makes all mutations fire change notifications"""
        return getattr(self, '_observe_mutations', False)

    @observe_mutations.setter
    def observe_mutations(self, value):
        if not isinstance(value, bool):
            raise TypeError('observe_mutations must be a boolean')
        self._observe_mutations = value

    @property
    def key_prop(self):
        """Property type allowed for keys"""
        return getattr(self, '_key_prop', basic.Property(''))

    @key_prop.setter
    def key_prop(self, value):
        self._key_prop = validate_prop(value)

    @property
    def value_prop(self):
        """Property type allowed for values"""
        return getattr(self, '_value_prop', basic.Property(''))

    @value_prop.setter
    def value_prop(self, value):
        self._value_prop = validate_prop(value)

    @property
    def name(self):
        return getattr(self, '_name', '')

    @name.setter
    def name(self, value):
        if self.key_prop:
            self.key_prop.name = value
        if self.value_prop:
            self.value_prop.name = value
        self._name = value

    @property
    def info(self):
        """Supplemental description of the list, with length and type"""
        itext = self.class_info
        if self.key_prop.info and self.value_prop.info:
            itext += ' (keys: {}; values: {})'.format(
                self.key_prop.info, self.value_prop.info
            )
        elif self.key_prop.info:
            itext += ' (keys: {})'.format(self.key_prop.info)
        elif self.value_prop.info:
            itext += ' (values: {})'.format(self.value_prop.info)
        return itext

    def validate(self, instance, value):
        if not isinstance(value, dict):
            self.error(instance, value)
        out = {}
        for key, val in iteritems(value):
            if self.key_prop:
                try:
                    key = self.key_prop.validate(instance, key)
                except ValueError:
                    self.error(instance, key, extra='This key is invalid.')
            if self.value_prop:
                try:
                    val = self.value_prop.validate(instance, val)
                except ValueError:
                    self.error(instance, val, extra='This value is invalid.')
            out[key] = val
        value = out
        if not self.observe_mutations:
            return value
        value = OBSERVABLE[self._class_default](value)
        value._name = self.name
        value._instance = instance
        return value

    def assert_valid(self, instance, value=None):
        """Check if dict and contained properties are valid"""
        valid = super(Dict, self).assert_valid(instance, value)
        if not valid:
            return False
        if value is None:
            value = instance._get(self.name)
        if value is None:
            return True
        if self.key_prop or self.value_prop:
            for key, val in iteritems(value):
                if self.key_prop:
                    self.key_prop.assert_valid(instance, key)
                if self.value_prop:
                    self.value_prop.assert_valid(instance, val)
        return True

    def serialize(self, value, **kwargs):
        """Return a serialized copy of the dict"""
        kwargs.update({'include_class': kwargs.get('include_class', True)})
        if self.serializer is not None:
            return self.serializer(value, **kwargs)
        if value is None:
            return None
        serial_tuples = [
            (
                self.key_prop.serialize(key, **kwargs),
                self.value_prop.serialize(val, **kwargs)
            )
            for key, val in iteritems(value)
        ]
        try:
            serial_dict = {key: val for key, val in serial_tuples}
        except TypeError as er:
            raise TypeError('Dict property {} cannot be serialized. '
                            'Serialized keys contain {}'.format(self.name, er))
        return serial_dict

    def deserialize(self, value, **kwargs):
        """Return a deserialized copy of the dict"""
        kwargs.update({'trusted': kwargs.get('trusted', False)})
        if self.deserializer is not None:
            return self.deserializer(value, **kwargs)
        if value is None:
            return None
        output_tuples = [
            (
                self.key_prop.deserialize(key, **kwargs),
                self.value_prop.deserialize(val, **kwargs)
            )
            for key, val in iteritems(value)
        ]
        try:
            output_dict = {key: val for key, val in output_tuples}
        except TypeError as er:
            raise TypeError('Dict property {} cannot be deserialized. '
                            'Keys contain {}'.format(self.name, er))
        return self._class_default(output_dict)

    def equal(self, value_a, value_b):
        try:
            if len(value_a) != len(value_b):
                return False
            copy_b = value_b.copy()
            for key_a in value_a:
                if self.value_prop.equal(value_a[key_a], value_b[key_a]):
                    copy_b.pop(key_a)
            return len(copy_b) == 0
        except (KeyError, TypeError, AttributeError):
            return False


    @staticmethod
    def to_json(value, **kwargs):
        """Return a copy of the dictionary

        If the values are HasProperties instances, they are serialized
        """
        serial_dict = {
            key: (
                val.serialize(**kwargs) if isinstance(val, HasProperties)
                else val
            )
            for key, val in iteritems(value)

        }
        return serial_dict
