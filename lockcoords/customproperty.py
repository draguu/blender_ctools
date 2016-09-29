# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####


import bpy


class CollectionPropertyOperators(bpy.types.PropertyGroup):
    """CollectionPropertyに対する複数のオペレータを纏めて登録する。

    最初にregister_classでこのクラスを登録しておく。
    >>> bpy.utils.register_class(CollectionPropertyOperators)

    bpy.ops.wm.collection_add(data_path='', function='')
    bpy.ops.wm.collection_remove(data_path='', function='', index=0)
    bpy.ops.wm.collection_clear(data_path='', function='')
    bpy.ops.wm.collection_move(data_path='', function='', index_from=0,
                               index_to=0)

    data_path引数を指定するとcontext属性を参照する。
    function引数を使う場合は、事前にregister_functionクラスメソッドで関数を
    登録しておく。
    """

    class _OperatorCollection:
        bl_description = ''
        bl_options = {'REGISTER'}

        _functions = None
        """:type: dict"""

        data_path = bpy.props.StringProperty(options={'SKIP_SAVE'})
        function = bpy.props.StringProperty(options={'SKIP_SAVE'})

        @classmethod
        def register_function(cls, key, func):
            cls._functions[key] = func

        @classmethod
        def register(cls):
            mod, func = cls.bl_idname.split('.')
            name = mod.upper() + '_OT_' + func.lower()
            cls_ = getattr(bpy.types, name)
            if cls == cls_:
                cls._functions = {}
            else:
                cls._functions = cls_._functions

        @classmethod
        def unregister(cls):
            cls._functions = None

    class Add(_OperatorCollection, bpy.types.Operator):
        """
        hoge = []
        def add_item(context):
            hoge.append({'fuga': 1, 'piyo': 2})
        OperatorCollectionAdd.register_function('list_hoge', add_item)
        bpy.ops.wm.collection_add(function='list_hoge')
        """

        bl_idname = 'wm.collection_add'
        bl_label = 'Collection Add'

        def execute(self, context):
            self._functions[self.function](context)
            return {'FINISHED'}

    class Remove(_OperatorCollection, bpy.types.Operator):
        """
        hoge = []
        def remove_item(context, index):
            hoge[:] = hoge[:index] + hoge[index + 1:]
        OperatorCollectionAdd.register_function('list_hoge', remove_item)
        bpy.ops.wm.collection_remove(function='list_hoge')
        """

        bl_idname = 'wm.collection_remove'
        bl_label = 'Collection Remove'

        index = bpy.props.IntProperty(options={'SKIP_SAVE'})

        def execute(self, context):
            if self.data_path:
                collection = eval('bpy.context.' + self.data_path)
                collection.remove(self.index)
            else:
                self._functions[self.function](context, self.index)
            return {'FINISHED'}

    class Clear(_OperatorCollection, bpy.types.Operator):
        bl_idname = 'wm.collection_clear'
        bl_label = 'Collection Clear'

        def execute(self, context):
            if self.data_path:
                collection = eval('bpy.context.' + self.data_path)
                collection.clear()
            else:
                self._functions[self.function](context)
            return {'FINISHED'}

    class Move(_OperatorCollection, bpy.types.Operator):
        bl_idname = 'wm.collection_move'
        bl_label = 'Collection Move'

        index_from = bpy.props.IntProperty(options={'SKIP_SAVE'})
        index_to = bpy.props.IntProperty(options={'SKIP_SAVE'})

        def execute(self, context):
            if self.data_path:
                collection = eval('bpy.context.' + self.data_path)
                collection.move(self.index_from, self.index_to)
            else:
                self._functions[self.function](context, self.index_from,
                                               self.index_to)
            return {'FINISHED'}

    classes = [
        Add,
        Remove,
        Clear,
        Move,
    ]

    @classmethod
    def register(cls):
        for c in cls.classes:
            bpy.utils.register_class(c)

    @classmethod
    def unregister(cls):
        for c in cls.classes:
            bpy.utils.unregister_class(c)


class PyCustomProperties(bpy.types.PropertyGroup):
    """あらかじめ型やインスタンスに対応するプロパティを設定しておいて、
    draw関数の中での動的なプロパティ追加を可能にする。
    詳しくはtest()関数を参照。

    # PointerProperty
    bpy.types.WindowManager.custom_props = bpy.props.PointerProperty(
        type=PyCustomProperties)

    # 例
    class Hoge:
        a = 1
    hoge = Hoge()
    class AddonPrefs(bpy.types.AddonPreferences):
        def draw(self, context):
            layout = self.layout
            PyCustomProperties.register_property(Hoge, 'a',
                                                 bpy.props.IntProperty())
            attrs = PyCustomProperties.ensure(hoge)
            layout.prop(PyCustomProperties.active(), attrs['a'])
    """

    # # Logger
    # import logging
    # logger = logging.getLogger(__name__).getChild(__qualname__)
    # """:type: logging.Logger"""
    # logger.propagate = False
    # logger.setLevel(logging.DEBUG)
    # for handler in list(logger.handlers):
    #     logger.removeHandler(handler)
    # handler = logging.StreamHandler()
    # handler.setLevel(logging.NOTSET)
    # formatter = logging.Formatter(
    #     '[%(levelname)s] '
    #     '[%(name)s.%(funcName)s():%(lineno)d]: '
    #     '%(message)s')
    # handler.setFormatter(formatter)
    # logger.addHandler(handler)
    # del handler, formatter
    #
    # @property
    # def logger_level(self):
    #     return self.logger.level
    #
    # @logger_level.setter
    # def logger_level(self, level):
    #     self.logger.setLevel(level)

    _props_attr = 'custom_props'

    # 同名のクラスで共有する値。registerの際に初期化
    _common_data = None
    """:type: dict"""

    def fget(self):
        return False
    def fset(self, value):
        common_data = self.__class__._common_data
        if common_data['attr'] is not None and value:
            attr, prop = common_data['attr']
            for cls in common_data['classes']:
                setattr(cls, attr, prop)
            common_data['attrs'][attr] = prop
            common_data['attr'] = None
    setattr = bpy.props.BoolProperty(get=fget, set=fset)
    del fget, fset

    @staticmethod
    def _hashable(obj):
        try:
            hash(obj)
            return True
        except TypeError:  # e.g. TypeError: unhashable type: 'list'
            return False

    @classmethod
    def _common_data_init(cls):
        cls_ = getattr(bpy.types, cls.__name__)
        if cls_ == cls:
            cls._common_data = {
                'classes': [],
                'object_props': {},
                'attr': None,  # setattrで使用する。[key, value]
                'attrs': {},  # 追加した属性
            }
        else:
            cls._common_data = cls_._common_data

    @classmethod
    def _custom_props_init(cls):
        if cls._common_data is None:
            cls._common_data_init()
        classes = cls._common_data['classes']
        cls_ = classes[0] if classes else cls
        setattr(bpy.types.WindowManager, cls._props_attr,
                bpy.props.PointerProperty(type=cls_))

    @classmethod
    def _custom_props_del(cls):
        if hasattr(bpy.types.WindowManager, cls._props_attr):
            delattr(bpy.types.WindowManager, cls._props_attr)

    @classmethod
    def active(cls):
        """:rtype: PyCustomProperties"""
        return getattr(bpy.context.window_manager, cls._props_attr)

    @classmethod
    def register_property(cls, obj, attr, prop):
        """プロパティを登録する
        :param obj: インスタンスかそのクラス
        :type obj: T
        :param attr: 属性名の文字列。コンテナのキー等の場合は角括弧で囲む。
            例: 'attr', '["key"]', '[2]', 'collection[5]', 'foo.bar.baz'
        :type attr: str
        :param prop: (bpy.props.BoolProperty, {'name': 'Test', ...})
        :type prop: tuple
        """
        if 'get' in prop[1] or 'set' in prop[1]:
            msg = '{}: {}: {}: get, set の関数は設定してはいけない'.format(
                obj, attr, prop
            )
            raise ValueError(msg)
        common_data = cls._common_data
        prop = (prop[0], prop[1].copy())
        id_value = id(obj)
        if cls._hashable(obj):
            if obj not in common_data['object_props']:
                common_data['object_props'][obj] = {}
            props = common_data['object_props'][obj]
            props[attr] = prop
            common_data['object_props'][id_value] = props
        else:
            if id_value not in common_data['object_props']:
                common_data['object_props'][id_value] = {}
            common_data['object_props'][id_value][attr] = prop

    @classmethod
    def ensure(cls, obj, *attributes):
        """各オブジェクト用のプロパティを追加する
        attrが空なら登録済みの属性を全て適用する
        """
        import inspect
        import traceback

        common_data = cls._common_data
        object_props = common_data['object_props']

        cls_ = obj.__class__
        props = {}
        if cls._hashable(cls_) and cls_ in object_props:
            props.update(object_props[cls_])
        if id(cls_) in object_props:
            props.update(object_props[id(cls_)])
        if cls._hashable(obj) and obj in object_props:
            props.update(object_props[obj])
        if id(obj) in object_props:
            props.update(object_props[id(obj)])

        attr_mapping = {}
        if not attributes:
            attributes = props.keys()
        for attr in attributes:
            if attr not in props:
                msg = "プロパティが未設定: {}: '{}'".format(obj, attr)
                raise ValueError(msg)

            if inspect.isclass(obj):
                name = obj.__name__
            else:
                name = obj.__class__.__name__
            wm_attr = '{}_{}_{}'.format(name, id(obj), attr)
            attr_mapping[attr] = wm_attr

            prop = (props[attr][0], props[attr][1].copy())
            # get, set 関数を有効としたためコメントアウト
            # # 既に存在するプロパティと差が無いなら飛ばす
            # if wm_attr in common_data['attrs']:
            #     prop_prev = common_data['attrs'][wm_attr]
            #     kwargs_prev = {k: v for k, v in prop_prev[1].items()
            #                    if k not in ('attr', 'get', 'set')}
            #     kwargs = {k: v for k, v in prop[1].items()
            #               if k not in ('attr', 'get', 'set')}
            #     if kwargs == kwargs_prev:
            #         continue

            # propertyのget,set関数を設定
            def gen(attr, wm_attr, prop):
                def get_value():
                    try:
                        if attr.startswith('['):
                            return eval('obj' + attr, {'obj': obj})
                        else:
                            return eval('obj.' + attr, {'obj': obj})
                    except:
                        traceback.print_exc()
                        return None

                def set_value(value):
                    try:
                        if attr.startswith('['):
                            code = 'obj{} = value'.format(attr)
                        else:
                            code = 'obj.{} = value'.format(attr)
                        exec(code, {'obj': obj, 'value': value})
                    except:
                        traceback.print_exc()

                def fget(self):
                    bl_rna = self.__class__.bl_rna
                    p = bl_rna.properties[wm_attr]

                    if prop[0] == bpy.props.EnumProperty:
                        items = prop[1]['items']
                        is_function = inspect.isfunction(items)
                        if is_function:
                            items = items(self, bpy.context)

                        value = get_value()

                        if p.is_enum_flag:
                            def set_to_int(value):
                                r = 0
                                for i, (identifier, *_) in enumerate(items):
                                    try:
                                        if identifier in value:
                                            r += 1 << i
                                    except:
                                        return -1
                                return r

                            if isinstance(value, (str, bytes)):
                                value = None
                            int_value = set_to_int(value)
                            if int_value == -1:
                                if is_function:
                                    int_value = 0
                                else:
                                    int_value = set_to_int(p.default_flag)
                            return int_value

                        else:
                            def str_to_int(value):
                                for i, (identifier, *_) in enumerate(items):
                                    if identifier == value:
                                        return i
                                return -1

                            int_value = str_to_int(value)
                            if int_value == -1:
                                if is_function:
                                    int_value = 0
                                else:
                                    int_value = str_to_int(p.default)
                            return int_value
                    else:
                        value = get_value()
                        if getattr(p, 'is_array', False):
                            is_invalid = value is None
                            try:
                                if len(value) != p.array_length:
                                    is_invalid = True
                            except:
                                is_invalid = True
                            if is_invalid:
                                value = tuple(p.default_array)
                        else:
                            if value is None:
                                value = p.default

                        if value is None:
                            if getattr(p, 'is_array', False):
                                value = list(p.default_array)
                            else:
                                value = p.default
                        return value

                def fset(self, value):
                    bl_rna = self.__class__.bl_rna
                    p = bl_rna.properties[wm_attr]

                    if prop[0] == bpy.props.EnumProperty:
                        items = prop[1]['items']
                        if inspect.isfunction(items):
                            items = items(self, bpy.context)
                        if p.is_enum_flag:
                            identifiers = []
                            for i, (identifier, *_) in enumerate(items):
                                if (1 << i) & value:
                                    identifiers.append(identifier)
                            # 型を合わせる
                            prev_value = get_value()
                            if isinstance(prev_value, tuple):
                                set_value(tuple(identifiers))
                            elif isinstance(prev_value, set):
                                set_value(set(identifiers))
                            else:
                                set_value(identifiers)
                        else:
                            for i, (identifier, *_) in enumerate(items):
                                if i == value:
                                    set_value(identifier)
                    else:
                        if getattr(p, 'is_array', False):
                            # 型を合わせる
                            prev_value = get_value()
                            if isinstance(prev_value, tuple):
                                set_value(value)  # tuple
                            else:
                                set_value(list(value))
                        else:
                            set_value(value)

                return fget, fset

            fget, fset = gen(attr, wm_attr, prop)
            if 'get' not in prop[1]:
                prop[1]['get'] = fget
            if 'set' not in prop[1]:
                prop[1]['set'] = fset

            # 属性追加
            common_data['attr'] = [wm_attr, prop]
            custom_props = cls.active()
            custom_props.setattr = True

        return attr_mapping

    @classmethod
    def register(cls):
        cls._common_data_init()
        common_data = cls._common_data
        common_data['classes'].append(cls)
        for attr, value in common_data['attrs'].items():
            setattr(cls, attr, value)
        cls._custom_props_init()

    @classmethod
    def unregister(cls):
        common_data = cls._common_data
        for attr in common_data['attrs']:
            delattr(cls, attr)
        common_data['classes'].remove(cls)
        if common_data['classes']:
            cls._custom_props_init()
        else:
            cls._custom_props_del()
        cls._common_data = None


def test():
    """実行すると3DViewのPropertiesパネルにCustomPanelが表示され、
    端末にpython objectの各属性の値が出力される。
    >>> import customproperty
    >>> customproperty.test()
    """

    if hasattr(bpy.types, PyCustomProperties.__name__):
        bpy.utils.unregister_class(
            getattr(bpy.types, PyCustomProperties.__name__))
    bpy.utils.register_class(PyCustomProperties)

    if hasattr(bpy.types, CollectionPropertyOperators.__name__):
        bpy.utils.unregister_class(
            getattr(bpy.types, CollectionPropertyOperators.__name__))
    bpy.utils.register_class(CollectionPropertyOperators)

    class CustomItem:
        def __init__(self):
            self.a = 1

    class CustomGroup:
        def __init__(self):
            self.int_value = 1
            self.float_value = 1.0
            self.bool_value = True

            self.int_array = [1,2,3]
            self.float_array = [1.0, 2.0, 3.0]
            self.bool_array = [True, False, True]

            self.enum = 'A'
            self.enum_flag = ['A', 'B']
            self.enum_flag_func = {'invalidvalue', 'B'}  # わざと不正な値を含めている

            self.item_list = []

    group = CustomGroup()

    class CustomPanel(bpy.types.Panel):
        bl_label = 'Custom Panel'
        bl_idname = 'CustomPanel'
        bl_space_type = 'VIEW_3D'
        bl_region_type = 'UI'

        def draw(self, context):
            # プロパティの登録
            custom_props = PyCustomProperties.active()
            custom_props.register_property(
                CustomGroup, 'int_value', bpy.props.IntProperty())
            custom_props.register_property(
                CustomGroup, 'float_value', bpy.props.FloatProperty())
            custom_props.register_property(
                CustomGroup, 'bool_value', bpy.props.BoolProperty())

            custom_props.register_property(
                CustomGroup, 'int_array',
                bpy.props.IntVectorProperty(size=2))
            custom_props.register_property(
                CustomGroup, 'float_array',
                bpy.props.FloatVectorProperty(size=3))
            custom_props.register_property(
                CustomGroup, 'bool_array',
                bpy.props.BoolVectorProperty(size=3))

            custom_props.register_property(
                CustomGroup, 'bool_array[1]',
                bpy.props.BoolProperty()
            )

            custom_props.register_property(
                CustomGroup, 'enum',
                bpy.props.EnumProperty(
                    items=[('A', 'A', ''), ('B', 'B', ''), ('C', 'C', '')]))
            custom_props.register_property(
                CustomGroup, 'enum_flag',
                bpy.props.EnumProperty(
                    items=[('A', 'A', ''), ('B', 'B', ''), ('C', 'C', '')],
                    options={'ENUM_FLAG'}))
            def items_get(self, context):
                items = [('A', 'A', ''), ('B', 'B', ''), ('C', 'C', '')]
                items_get._items = items
                return items
            custom_props.register_property(
                CustomGroup, 'enum_flag_func',
                bpy.props.EnumProperty(items=items_get, options={'ENUM_FLAG'}))

            layout = self.layout

            # 描画
            attrs = custom_props.ensure(group)
            layout.prop(custom_props, attrs['int_value'])
            layout.prop(custom_props, attrs['float_value'])
            layout.prop(custom_props, attrs['bool_value'])

            layout.prop(custom_props, attrs['int_array'])
            layout.prop(custom_props, attrs['float_array'])
            layout.prop(custom_props, attrs['bool_array'])

            layout.prop(custom_props, attrs['bool_array[1]'])

            layout.prop(custom_props, attrs['enum'])
            layout.prop(custom_props, attrs['enum_flag'])
            layout.prop(custom_props, attrs['enum_flag_func'])

            # group.item_listの登録と描画

            # CustomGroup.item_listへの要素を追加するオペレータの登録
            identifier = str(id(group)) + '_collection'
            def item_add_func(context, group=group):
                group.item_list.append(CustomItem())
            CollectionPropertyOperators.Add.register_function(
                identifier, item_add_func)
            # ボタン描画
            op = layout.operator('wm.collection_add', text='Add')
            op.function = identifier

            def draw_item(layout, obj):
                custom_props.register_property(
                    CustomItem, 'a', bpy.props.IntProperty())
                attrs = custom_props.ensure(obj)
                layout.prop(custom_props, attrs['a'])

            column = layout.column()

            # group.item_listの個々の要素に対しての処理
            for i, item in enumerate(group.item_list):
                row = column.box().row()

                # Draw CustomItem
                draw_item(row.column(), item)

                sub = row.row(align=True)

                identifier = str(id(item))

                # Register Up / Down
                def item_move_func(context, index_from, index_to, group=group):
                    item = group.item_list[index_from]
                    group.item_list[index_from: index_from + 1] = []
                    group.item_list.insert(index_to, item)
                CollectionPropertyOperators.Move.register_function(
                    identifier, item_move_func)
                # Up
                op = sub.operator('wm.collection_move', text='',
                                  icon='TRIA_UP')
                op.function = identifier
                op.index_from = i
                op.index_to = max(0, i - 1)
                # Down
                op = sub.operator('wm.collection_move', text='',
                                  icon='TRIA_DOWN')
                op.function = identifier
                op.index_from = i
                op.index_to = min(i + 1, len(group.item_list) - 1)

                # Register Delete
                def item_remove_func(context, index, group=group):
                    group.item_list[index: index + 1] = []

                CollectionPropertyOperators.Remove.register_function(
                    identifier, item_remove_func)
                # Delete
                op = sub.operator('wm.collection_remove', text='',
                                  icon='X')
                op.function = identifier
                op.index = i

            for attr in ['int_value', 'float_value', 'bool_value',
                         'int_array', 'float_array', 'bool_array',
                         'enum', 'enum_flag', 'enum_flag_func']:
                print("'{}': {}".format(attr, getattr(group, attr)))
            for i, item in enumerate(group.item_list):
                print("{}: 'a': {}".format(i, item.a))
            print()

    if hasattr(bpy.types, CustomPanel.__name__):
        bpy.utils.unregister_class(getattr(bpy.types, CustomPanel.__name__))
    bpy.utils.register_class(CustomPanel)
