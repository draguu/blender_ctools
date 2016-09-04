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

# <pep8-80 compliant>

__all__ = (
    "paths",
    "modules",
    "check",
    "enable",
    "disable",
    "reset_all",
    "module_bl_info",
)

import bpy as _bpy
_user_preferences = _bpy.context.user_preferences

error_duplicates = False
error_encoding = False
addons_fake_modules = {}


class AddonRegisterInfo:
    if 'DYNAMIC_PROPERTY_ATTR' in globals():
        DYNAMIC_PROPERTY_ATTR = DYNAMIC_PROPERTY_ATTR
    else:
        DYNAMIC_PROPERTY_ATTR = ''

    @staticmethod
    def name_mangling(class_name, attr):
        if not attr.startswith('__') or attr.endswith('__'):
            return attr
        if not isinstance(class_name, str):  # クラスオブジェクトを想定
            class_name = class_name.__name__
        return '_' + class_name.lstrip('_') + attr

    @classmethod
    def derive(cls, bl_idname=None, lock_default_keymap_items=None):
        """クラス属性を変更した新しいクラスを生成して返す。__new__や__init__が
        使えないので苦肉の策
        直接継承せずにこれで生成したクラスを使う
        :rtype: AddonRegisterInfo
        """
        attrs = {
            'keymap_items': [],
            cls.name_mangling(cls.__name__, '__default_keymap_items'): [],
            cls.name_mangling(cls.__name__, '__default_keymap_item_values'): [],
            'addon_classes': [],
            'addon_attributes': [],
        }
        if bl_idname is not None:
            attrs['bl_idname'] = bl_idname
        if lock_default_keymap_items is not None:
            key = cls.name_mangling(cls.__name__,
                                    '__lock_default_keymap_items')
            attrs[key] = lock_default_keymap_items
        t = type(cls.__name__, (cls,), attrs)
        return t

    IGRORE_ADDONS = ['CTools']  # bl_info['name']
    ADDON_REGISTER_INFO = True  # この属性の有無でインスタンスを判別する
    IDPROP_NAME = 'AddonKeyMapUtility_keymap_items'

    bl_idname = ''
    __lock_default_keymap_items = False

    # [(km.name, kmi.id), ...]
    keymap_items = []
    """:type: list[(str, int)]"""

    # keymaps_set_default()の際に_keymap_itemsを複製
    # [(km.name, kmi.id), ...]
    __default_keymap_items = []
    """:type: list[(str, int)]"""

    # get_keymap_item_values()の返り値。
    __default_keymap_item_values = []

    addon_classes = []
    """:type: list[str]"""

    addon_attributes = []
    """:type: list[(str, str)]"""

    def __get_wm_prop(self):
        wm = _bpy.context.window_manager
        # NOTE: self.bl_idname は '\x06' となっている
        return getattr(wm.addon_register_information,
                       self.__class__.bl_idname.replace('.', '_'))

    # register / unregister -----------------------------------------
    @classmethod
    def register(cls):
        """継承したクラスでもregisterを定義するなら、super関数を使って
        このメソッドを呼ぶ。
        super().register()
        """
        classes = [cls._OperatorKeymapItemAdd,
                   cls._OperatorKeymapItemRemove,
                   cls._OperatorKeymapsWrite,
                   cls._OperatorKeymapsRestore,
                   cls._MenuKeymapItemAdd,
                   cls._AddonRegisterInformation,
                   cls._AddonRegisterInformationUI,
                   ]
        for c in classes:
            c.register_class()

        c = getattr(_bpy.types, cls._AddonRegisterInformation.__name__)
        _bpy.types.WindowManager.addon_register_information = \
            _bpy.props.PointerProperty(type=c)

        c = super()
        if hasattr(c, 'register'):
            c.register()

    @classmethod
    def unregister(cls):
        """注意事項はregisterと同じ"""

        classes = [cls._OperatorKeymapItemAdd,
                   cls._OperatorKeymapItemRemove,
                   cls._OperatorKeymapsWrite,
                   cls._OperatorKeymapsRestore,
                   cls._MenuKeymapItemAdd,
                   cls._AddonRegisterInformation,
                   cls._AddonRegisterInformationUI,
                   ]
        for c in classes[::-1]:
            c.unregister_class()

        if not hasattr(_bpy.types, cls._AddonRegisterInformation.__name__):
            del _bpy.types.WindowManager.addon_register_information

        c = super()
        if hasattr(c, 'unregister'):
            c.unregister()

    @staticmethod
    def get_keymap(name):
        """KeyMaps.new()の結果を返す。name以外の引数は勝手に補間してくれる。
        :type name: str
        :rtype: _bpy.types.KeyMap
        """
        import bpy_extras.keyconfig_utils

        # blenderを起動してis_modalを確認するしか方法が無い
        modal_keymaps = {
            'View3D Gesture Circle', 'Gesture Border',
            'Gesture Zoom Border', 'Gesture Straight Line',
            'Standard Modal Map', 'Knife Tool Modal Map',
            'Transform Modal Map', 'Paint Stroke Modal', 'View3D Fly Modal',
            'View3D Walk Modal', 'View3D Rotate Modal', 'View3D Move Modal',
            'View3D Zoom Modal', 'View3D Dolly Modal', }

        kc = _bpy.context.window_manager.keyconfigs.addon
        if not kc:
            return None

        # if 'INVALID_MODAL_KEYMAP' and name in modal_keymaps:
        #     msg = "not support modal keymap: '{}'".format(name)
        #     raise ValueError(msg)

        def get(ls, name):
            for keymap_name, space_type, region_type, children in ls:
                if keymap_name == name:
                    is_modal = keymap_name in modal_keymaps
                    return kc.keymaps.new(keymap_name, space_type=space_type,
                                          region_type=region_type,
                                          modal=is_modal)
                elif children:
                    km = get(children, name)
                    if km:
                        return km

        km = get(bpy_extras.keyconfig_utils.KM_HIERARCHY, name)
        if not km:
            msg = "Keymap '{}' not in builtins".format(name)
            raise ValueError(msg)
        return km

    @classmethod
    def get_instance(cls):
        """AddonPreferencesのインスタンスを返す。二階層までしか対応しない。
        :rtype: AddonPreferences
        """
        if 0:
            name = cls.bl_idname
            attrs = name.split('.')
            prefs = _bpy.context.user_preferences.addons[attrs[0]].preferences
            for attr in attrs[1:]:
                prefs = getattr(prefs, attr)
            return prefs

        U = _bpy.context.user_preferences
        if '.' in cls.bl_idname:
            # ctools以外での使用を想定していない
            base_name, sub_name = cls.bl_idname.split('.')
            base_prefs = U.addons[base_name].preferences
            if cls.DYNAMIC_PROPERTY_ATTR:
                addons = getattr(base_prefs, cls.DYNAMIC_PROPERTY_ATTR)
                return getattr(addons, sub_name)
            else:
                return getattr(base_prefs, sub_name)
        else:
            return U.addons[cls.bl_idname].preferences

    @staticmethod
    def __verify_keyconfigs():
        return _bpy.context.window_manager.keyconfigs.addon is not None

    @classmethod
    def __reversed_keymap_table(cls):
        """KeyMapItemがキー、KeyMapが値の辞書を返す"""
        if not cls.__verify_keyconfigs():
            return
        kc = _bpy.context.window_manager.keyconfigs.addon
        km_table = {}
        for km in kc.keymaps:
            for kmi in km.keymap_items:
                km_table[kmi] = km
        return km_table

    @classmethod
    def keymap_items_get_attributes(cls):
        """
        :return: [[keymap_name, attrs, props], ...]
            第一要素はkeymap名。
            第二要素はKeymapItemの属性名(activeやshift等)とその値の辞書。
            第三要素はそのキーマップに割り当てられたオペレータのプロパティーの
            辞書。is_property_set()で判定して、未変更ならその値は辞書に含めない
        :rtype: list
        """
        import itertools
        import mathutils

        if not cls.__verify_keyconfigs():
            return

        values = []
        km_table = cls.__reversed_keymap_table()

        keympap_items = []
        for item in list(cls.keymap_items):
            km_name, kmi_id = item
            km = cls.get_keymap(km_name)
            for kmi in km.keymap_items:
                if kmi.id == kmi_id:
                    keympap_items.append(kmi)
                    break

        for kmi in keympap_items:
            km = km_table[kmi]
            # KeyMapItemの属性
            attrs = {}
            for attr in ('active', 'map_type', 'type', 'value', 'propvalue',
                         'idname', 'any', 'shift', 'ctrl', 'alt', 'oskey',
                         'key_modifier'):
                value = getattr(kmi, attr)
                if isinstance(value, bool):
                    value = int(value)
                attrs[attr] = value
            # オペレータのプロパティ
            op_props = {}
            if not km.is_modal:
                for attr in kmi.properties.bl_rna.properties.keys():
                    if attr == 'rna_type':
                        continue
                    if kmi.properties.is_property_set(attr):
                        value = getattr(kmi.properties, attr)
                        if isinstance(value, bool):
                            value = int(value)
                        elif isinstance(value, (
                                mathutils.Color, mathutils.Euler,
                                mathutils.Vector, mathutils.Quaternion)):
                            value = list(value)
                        elif isinstance(value, mathutils.Matrix):
                            value = list(
                                itertools.chain.from_iterable(value.col))
                        op_props[attr] = value

            values.append([km.name, attrs, op_props])

        return values

    @classmethod
    def keymap_items_set_attributes(cls, values, set_default=False):
        import traceback
        if not cls.__verify_keyconfigs():
            return
        cls.keymap_items_remove()
        keymap_items = []
        for km_name, attrs, op_props in values:
            km = cls.get_keymap(km_name)
            if 'INVALID_MODAL_KEYMAP' and km.is_modal:
                raise ValueError(
                    "not support modal keymap: '{}'".format(km.name))
            if km.is_modal:
                args = {name: attrs[name] for name in (
                    'type', 'value', 'propvalue', 'any', 'shift', 'ctrl',
                    'alt', 'oskey', 'key_modifier')}
                kmi = km.keymap_items.new_modal(**args)
                # kmi.propvalue = attrs['propvalue']  # 適用できていないから
                # TODO: ModalKeyMap使用不可。
                #       val: enum "TRANSLATE" not found in ('NONE')
            else:
                args = {name: attrs[name] for name in (
                    'idname', 'type', 'value', 'any', 'shift', 'ctrl', 'alt',
                    'oskey', 'key_modifier')}
                kmi = km.keymap_items.new(**args)
            kmi.active = attrs['active']
            for name, value in op_props.items():
                try:
                    setattr(kmi.properties, name, value)
                except:
                    traceback.print_exc()
            keymap_items.append(kmi)
        cls.keymap_items_add(keymap_items, set_default, False)

    @classmethod
    def keymap_item_add(cls, kmi):
        """KeyMapItemを登録する
        :param kmi: KeyMapItem 若しくは (KeyMap名, KeyMapItemのid)
        :type kmi: _bpy.types.KeyMapItem | (str, int)
        """
        if not cls.__verify_keyconfigs():
            return
        if isinstance(kmi, _bpy.types.KeyMapItem):
            km_tabel = cls.__reversed_keymap_table()
            km = km_tabel[kmi]
        else:
            km, kmi = kmi
        if 'INVALID_MODAL_KEYMAP' and km.is_modal:
            raise ValueError("not support modal keymap: '{}'".format(km.name))
        cls.keymap_items.append((km.name, kmi.id))

    @classmethod
    def keymap_items_add(cls, addon_keymaps, set_default=True,
                         load=True):
        """KeyMapItemを登録する。keymaps_set_default(), keymaps_load() も
        まとめて行う。
        :param addon_keymaps: KeyMapItem 若しくは (KeyMap名, KeyMapItemのid) の
            リスト
        :type addon_keymaps: list[_bpy.types.KeyMapItem] | list[(str, int)]
        """
        if not cls.__verify_keyconfigs():
            return
        km_tabel = cls.__reversed_keymap_table()
        items = []
        for kmi in addon_keymaps:
            if isinstance(kmi, _bpy.types.KeyMapItem):
                km = km_tabel[kmi]
            else:
                km, kmi = kmi
            if 'INVALID_MODAL_KEYMAP' and km.is_modal:
                raise ValueError(
                    "not support modal keymap: '{}'".format(km.name))
            items.append((km.name, kmi.id))
        cls.keymap_items.extend(items)
        if set_default:
            cls.keymap_items_set_default()
        if load:
            cls.keymap_items_load()

    @classmethod
    def keymap_item_remove(cls, kmi, remove=True):
        """KeyMapItemの登録を解除する
        :param kmi: KeyMapItem 若しくは (KeyMap名, KeyMapItemのid)
        :type kmi: _bpy.types.KeyMapItem | (str, int)
        :param remove: KeyMapItemをKeyMapItemsから削除する
        :type remove: bool
        """
        if not cls.__verify_keyconfigs():
            return
        km_table = cls.__reversed_keymap_table()
        if isinstance(kmi, _bpy.types.KeyMapItem):
            km = km_table[kmi]
            item = (km.name, kmi.id)
        else:
            item = kmi
            km_name, kmi_id = item
            km = cls.get_keymap(km_name)
            for kmi in km.keymap_items:
                if kmi.id == kmi_id:
                    break
            else:
                raise ValueError('KeyMapItem not fond')
        if 'INVALID_MODAL_KEYMAP' and km.is_modal:
            raise ValueError("not support modal keymap: '{}'".format(km.name))
        cls.keymap_items.remove(item)
        if remove:
            km.keymap_items.remove(kmi)

    @classmethod
    def keymap_items_remove(cls, remove=True,
                            remove_only_added=False):
        """全てのKeyMapItemの登録を解除する。
        :param remove: KeyMapItemをKeyMap.keymap_itemsから削除する
        :type remove: bool
        :param remove_only_added:
            self._default_keymap_itemsに含まれないもののみ消す
        :type remove_only_added: bool
        """
        if not cls.__verify_keyconfigs():
            return
        if remove:
            for km_name, kmi_id in cls.keymap_items:
                if remove_only_added:
                    if (km_name, kmi_id) in cls.__default_keymap_items:
                        continue
                km = cls.get_keymap(km_name)
                for kmi in km.keymap_items:
                    if kmi.id == kmi_id:
                        break
                else:
                    raise ValueError('KeyMapItem not fond')
                if 'INVALID_MODAL_KEYMAP' and km.is_modal:
                    raise ValueError(
                        "not support modal keymap: '{}'".format(km.name))
                km.keymap_items.remove(kmi)
        cls.keymap_items.clear()

    @classmethod
    def keymap_items_set_default(cls):
        """現在登録しているKeyMapItemを初期値(restore時の値)とする"""
        cls.__default_keymap_item_values.clear()
        cls.__default_keymap_item_values[:] = \
            cls.keymap_items_get_attributes()
        cls.__default_keymap_items = cls.keymap_items[:]

    @classmethod
    def keymap_items_load(cls):
        """保存されたキーマップを読んで現在のキーマップを置き換える"""
        addon_prefs = cls.get_instance()
        if cls.IDPROP_NAME not in addon_prefs:
            return False
        cls.keymap_items_set_attributes(addon_prefs[cls.IDPROP_NAME])
        return True

    @classmethod
    def keymap_items_restore(cls):
        """キーマップを初期値に戻す"""
        cls.keymap_items_set_attributes(cls.__default_keymap_item_values, True)

    # classes -------------------------------------------------------
    @classmethod
    def addon_classes_add(cls, types):
        for t in types:
            if not isinstance(t, str):
                t = t.__name__
            cls.addon_classes.append(t)

    @classmethod
    def addon_classes_remove(cls):
        for class_name in cls.addon_classes:
            if hasattr(_bpy.types, class_name):
                cls_ = getattr(_bpy.types, class_name)
                _bpy.utils.unregister_class(cls_)
        cls.addon_classes.clear()

    # attributes ----------------------------------------------------
    @classmethod
    def addon_attributes_add(cls, attributes):
        cls.addon_attributes.extend(attributes)

    @classmethod
    def addon_attributes_remove(cls):
        for class_name, attr in cls.addon_attributes:
            cls_ = getattr(_bpy.types, class_name, None)
            if cls_:
                if hasattr(cls_, attr):
                    delattr(cls_, attr)
        cls.addon_attributes.clear()

    # draw ----------------------------------------------------------

    __EVENT_TYPES = set()
    __EVENT_TYPE_MAP = {}
    __EVENT_TYPE_MAP_EXTRA = {}

    __INDENTPX = 16

    def __indented_layout(self, layout, level):
        if level == 0:
            # Tweak so that a percentage of 0 won't split by half
            level = 0.0001
        indent = level * self.__INDENTPX / _bpy.context.region.width

        split = layout.split(percentage=indent)
        col = split.column()
        col = split.column()
        return col

    def __draw_entry(self, display_keymaps, entry, col, level=0):
        idname, spaceid, regionid, children = entry

        for km, km_items in display_keymaps:
            if (km.name == idname and km.space_type == spaceid and
                        km.region_type == regionid):
                self.__draw_km(display_keymaps, km, km_items, children, col,
                               level)

    def __draw_km(self, display_keymaps, km, km_items, children, layout,
                  level):
        from _bpy.app.translations import pgettext_iface as iface_
        from _bpy.app.translations import contexts as i18n_contexts

        # km = km.active()  # keyconfigs.userのkeymapが返ってくる

        layout.context_pointer_set("keymap", km)

        col = self.__indented_layout(layout, level)

        row = col.row(align=True)
        row.prop(km, "show_expanded_children", text="", emboss=False)
        row.label(text=km.name, text_ctxt=i18n_contexts.id_windowmanager)

        # if km.is_user_modified or km.is_modal:
        if km.is_modal:
            subrow = row.row()
            subrow.alignment = 'RIGHT'

            # if km.is_user_modified:
            #     subrow.operator("wm.keymap_restore", text="Restore")
            if km.is_modal:
                subrow.label(text="", icon='LINKED')
            del subrow

        if km.show_expanded_children:
            if children:
                # Put the Parent key map's entries in a 'global' sub-category
                # equal in hierarchy to the other children categories
                subcol = self.__indented_layout(col, level + 1)
                subrow = subcol.row(align=True)
                subrow.prop(km, "show_expanded_items", text="", emboss=False)
                subrow.label(text=iface_("%s (Global)") % km.name,
                             translate=False)
            else:
                km.show_expanded_items = True

            # Key Map items
            if km.show_expanded_items:
                kmi_level = level + 3 if children else level + 1
                # for kmi in km.keymap_items:
                for kmi in km_items:
                    self.__draw_kmi(km, kmi, col, kmi_level)

            # Child key maps
            if children:
                for entry in children:
                    self.__draw_entry(display_keymaps, entry, col,
                                      level + 1)

            col.separator()

    def __draw_kmi(self, km, kmi, layout, level):
        map_type = kmi.map_type

        col = self.__indented_layout(layout, level)

        if kmi.show_expanded:
            col = col.column(align=True)
            box = col.box()
        else:
            box = col.column()

        split = box.split(percentage=0.01)

        # header bar
        row = split.row()
        row.prop(kmi, "show_expanded", text="", emboss=False)

        row = split.row()
        row.prop(kmi, "active", text="", emboss=False)

        if km.is_modal:
            row.prop(kmi, "propvalue", text="")
        else:
            row.label(text=kmi.name)

        row = split.row()
        row.prop(kmi, "map_type", text="")
        if map_type == 'KEYBOARD':
            row.prop(kmi, "type", text="", full_event=True)
        elif map_type == 'MOUSE':
            row.prop(kmi, "type", text="", full_event=True)
        elif map_type == 'NDOF':
            row.prop(kmi, "type", text="", full_event=True)
        elif map_type == 'TWEAK':
            subrow = row.row()
            subrow.prop(kmi, "type", text="")
            subrow.prop(kmi, "value", text="")
        elif map_type == 'TIMER':
            row.prop(kmi, "type", text="")
        else:
            row.label()

        sub = row.row()
        op = sub.operator("wm.ari_keymap_item_remove", text="", icon='X')
        op.item_id = kmi.id
        if self.__lock_default_keymap_items:
            if (km.name, kmi.id) in self.__default_keymap_items:
                sub.enabled = False

        # Expanded, additional event settings
        if kmi.show_expanded:
            box = col.box()

            split = box.split(percentage=0.4)
            sub = split.row()

            if km.is_modal:
                sub.prop(kmi, "propvalue", text="")
            else:
                # One day...
                # ~ sub.prop_search(kmi, "idname", _bpy.context.window_manager,
                #  "operators_all", text="")
                sub.prop(kmi, "idname", text="")

            if map_type not in {'TEXTINPUT', 'TIMER'}:
                sub = split.column()
                subrow = sub.row(align=True)

                if map_type == 'KEYBOARD':
                    subrow.prop(kmi, "type", text="", event=True)
                    subrow.prop(kmi, "value", text="")
                elif map_type in {'MOUSE', 'NDOF'}:
                    subrow.prop(kmi, "type", text="")
                    subrow.prop(kmi, "value", text="")

                subrow = sub.row()
                subrow.scale_x = 0.75
                subrow.prop(kmi, "any")
                subrow.prop(kmi, "shift")
                subrow.prop(kmi, "ctrl")
                subrow.prop(kmi, "alt")
                subrow.prop(kmi, "oskey", text="Cmd")
                subrow.prop(kmi, "key_modifier", text="", event=True)

            # Operator properties
            box.template_keymap_item_properties(kmi)

    def __draw_filtered(self, display_keymaps, filter_type, filter_text,
                        layout):
        _EVENT_TYPES = self.__EVENT_TYPES
        _EVENT_TYPE_MAP = self.__EVENT_TYPE_MAP
        _EVENT_TYPE_MAP_EXTRA = self.__EVENT_TYPE_MAP_EXTRA

        if filter_type == 'NAME':
            def filter_func(kmi):
                return (filter_text in kmi.idname.lower() or
                        filter_text in kmi.name.lower())
        else:
            if not _EVENT_TYPES:
                enum = _bpy.types.Event.bl_rna.properties["type"].enum_items
                _EVENT_TYPES.update(enum.keys())
                _EVENT_TYPE_MAP.update(
                    {item.name.replace(" ", "_").upper(): key for key, item in
                     enum.items()})

                del enum
                _EVENT_TYPE_MAP_EXTRA.update(
                    {"`": 'ACCENT_GRAVE',
                     "*": 'NUMPAD_ASTERIX',
                     "/": 'NUMPAD_SLASH',
                     "RMB": 'RIGHTMOUSE',
                     "LMB": 'LEFTMOUSE',
                     "MMB": 'MIDDLEMOUSE',
                     })
                _EVENT_TYPE_MAP_EXTRA.update(
                    {"%d" % i: "NUMPAD_%d" % i for i in range(10)})
            # done with once off init

            filter_text_split = filter_text.strip()
            filter_text_split = filter_text.split()

            # Modifier {kmi.attribute: name} mapping
            key_mod = {"ctrl": "ctrl", "alt": "alt", "shift": "shift",
                       "cmd": "oskey", "oskey": "oskey", "any": "any",}
            # KeyMapItem like dict, use for comparing against
            # attr: {states, ...}
            kmi_test_dict = {}
            # Special handling of 'type' using a list if sets,
            # keymap items must match against all.
            kmi_test_type = []

            # initialize? - so if a if a kmi has a MOD assigned it wont show up.
            # ~ for kv in key_mod.values():
            # ~    kmi_test_dict[kv] = {False}

            # altname: attr
            for kk, kv in key_mod.items():
                if kk in filter_text_split:
                    filter_text_split.remove(kk)
                    kmi_test_dict[kv] = {True}

            # whats left should be the event type
            def kmi_type_set_from_string(kmi_type):
                kmi_type = kmi_type.upper()
                kmi_type_set = set()

                if kmi_type in _EVENT_TYPES:
                    kmi_type_set.add(kmi_type)

                if not kmi_type_set or len(kmi_type) > 1:
                    # replacement table
                    for event_type_map in (_EVENT_TYPE_MAP,
                                           _EVENT_TYPE_MAP_EXTRA):
                        kmi_type_test = event_type_map.get(kmi_type)
                        if kmi_type_test is not None:
                            kmi_type_set.add(kmi_type_test)
                        else:
                            # print("Unknown Type:", kmi_type)

                            # Partial match
                            for k, v in event_type_map.items():
                                if (kmi_type in k) or (kmi_type in v):
                                    kmi_type_set.add(v)
                return kmi_type_set

            for i, kmi_type in enumerate(filter_text_split):
                kmi_type_set = kmi_type_set_from_string(kmi_type)

                if not kmi_type_set:
                    return False

                kmi_test_type.append(kmi_type_set)
            # tiny optimization, sort sets so the smallest is first
            # improve chances of failing early
            kmi_test_type.sort(key=lambda kmi_type_set: len(kmi_type_set))

            # main filter func, runs many times
            def filter_func(kmi):
                for kk, ki in kmi_test_dict.items():
                    val = getattr(kmi, kk)
                    if val not in ki:
                        return False

                # special handling of 'type'
                for ki in kmi_test_type:
                    val = kmi.type
                    if val == 'NONE' or val not in ki:
                        # exception for 'type'
                        # also inspect 'key_modifier' as a fallback
                        val = kmi.key_modifier
                        if not (val == 'NONE' or val not in ki):
                            continue
                        return False

                return True

        for km, km_items in display_keymaps:
            # km = km.active()  # keyconfigs.userのkeymapが返ってくる
            layout.context_pointer_set("keymap", km)

            if filter_text:
                filtered_items = [kmi for kmi in km_items if filter_func(kmi)]
            else:
                filtered_items = km_items

            if filtered_items:
                col = layout.column()

                row = col.row()
                row.label(text=km.name, icon='DOT')

                for kmi in filtered_items:
                    self.__draw_kmi(km, kmi, col, 1)

        return True

    def __draw_hierarchy(self, display_keymaps, layout):
        from bpy_extras import keyconfig_utils
        for entry in keyconfig_utils.KM_HIERARCHY:
            self.__draw_entry(display_keymaps, entry, layout)

    def __draw_classes(self, context, layout, box=True):
        if box:
            col = layout.column().box()
        else:
            col = layout.column()

        row = col.row()

        # NOTE: register可能なクラスはRNA_def_struct_register_funcs()で
        #       regメンバに代入しているもの
        # registerable_classes = [
        #     bpy.types.AddonPreferences,
        #     bpy.types.Panel,
        #     bpy.types.UIList,
        #     bpy.types.Menu,
        #     bpy.types.Header,
        #     bpy.types.Operator,
        #     bpy.types.Macro,
        #     bpy.types.KeyingSetInfo,
        #     bpy.types.RenderEngine,
        #     bpy.types.PropertyGroup,
        #     bpy.types.Node,
        #     bpy.types.NodeCustomGroup,
        #     bpy.types.ShaderNode,
        #     bpy.types.CompositorNode,
        #     bpy.types.TextureNode,
        #     bpy.types.NodeSocket,
        #     bpy.types.NodeSocketInterface,
        #     bpy.types.NodeTree,
        # ]
        classes = []
        for class_name in self.addon_classes:
            if hasattr(_bpy.types, class_name):
                t = getattr(_bpy.types, class_name)
                for base in t.__bases__:
                    if issubclass(base, _bpy.types.bpy_struct):
                        classes.append((class_name, base))
                        break
                else:
                    classes.append((class_name, None))
            else:
                classes.append((class_name, None))
        classes.sort(key=lambda x: getattr(x[1], '__name__', ''))

        split = row.split(0.4)
        col1 = split.column()
        col_ = split.split(0.3)
        col2 = col_.column()
        col3 = col_.column()
        # col1 = row.column()
        # col2 = row.column()
        # col3 = row.column()
        for class_name, base_class in classes:
            col1.label(class_name)
            if hasattr(_bpy.types, class_name):
                t = getattr(_bpy.types, class_name)
                if t:
                    if base_class is not None:
                        col2.label(base_class.__name__)
                    else:
                        col2.separate()
                    col3.label(getattr(t, 'bl_label', ''))
                else:
                    col2.separate()
                    col3.separate()

    def __draw_attributes(self, context, layout, box=True):
        if box:
            col = layout.column().box()
        else:
            col = layout.column()

        attributes = self.addon_attributes[:]
        attributes.sort(key=lambda x: (x[0], x[1]))

        for class_name, attr in attributes:
            col.label(class_name + '.' + attr)

    def __draw_keymaps(self, context, layout, hierarchy=False, box=True):
        wm_prop = self.__get_wm_prop()
        addon_prefs = self.get_instance()
        space_pref = context.space_data

        if box:
            col = layout.column().box()
        else:
            col = layout.column()

        sub = col.column()

        subsplit = sub.split()
        subcol = subsplit.column()

        subcolsplit = subcol.split(percentage=0.7)  # 右側にwrite,restore

        display_keymaps = {}
        for item in list(self.keymap_items):
            km_name, kmi_id = item
            km = self.get_keymap(km_name)
            for kmi in km.keymap_items:
                if kmi.id == kmi_id:
                    break
            else:
                self.keymap_items.remove(item)
                continue
            items = display_keymaps.setdefault(km, [])
            items.append(kmi)
        for km, items in display_keymaps.items():
            ls = list(km.keymap_items)
            items.sort(key=ls.index)
        display_keymaps = list(display_keymaps.items())

        row = subcolsplit.row()
        rowsub = row.split(align=True, percentage=0.33)
        # postpone drawing into rowsub, so we can set alert!

        # col.separator()

        if 0:
            filter_type = space_pref.filter_type
            filter_text = space_pref.filter_text.strip()
        else:
            filter_type = wm_prop.filter_type
            filter_text = wm_prop.filter_text

        if filter_text or not hierarchy:
            filter_text = filter_text.lower()
            ok = self.__draw_filtered(display_keymaps, filter_type,
                                      filter_text, col)
        else:
            self.__draw_hierarchy(display_keymaps, col)
            ok = True

        colsub = col.split(percentage=0.2).column()
        colsub.operator("wm.ari_keymap_item_add", text="Add New",
                        icon='ZOOMIN')

        # go back and fill in rowsub
        if 0:
            rowsub.prop(space_pref, "filter_type", text="")
        else:
            rowsub.prop(wm_prop, 'filter_type', text="")
        rowsubsub = rowsub.row(align=True)
        if not ok:
            rowsubsub.alert = True
        if 0:
            rowsubsub.prop(space_pref, "filter_text", text="", icon='VIEWZOOM')
        else:
            rowsubsub.prop(wm_prop, 'filter_text', text="", icon='VIEWZOOM')

        # Write / Restore
        default_km = self.__default_keymap_item_values
        current_km = self.keymap_items_get_attributes()
        if self.IDPROP_NAME in addon_prefs:
            def idprop_to_py(prop):
                if isinstance(prop, list):
                    return [idprop_to_py(p) for p in prop]
                elif hasattr(prop, 'to_dict'):
                    return prop.to_dict()
                elif hasattr(prop, 'to_list'):
                    return prop.to_list()
                else:
                    return prop

            prop = addon_prefs[self.IDPROP_NAME]
            idp_km = idprop_to_py(prop)
        else:
            idp_km = None
        subcolsplitrow = subcolsplit.row().split(align=True)
        # Write
        subcolsplitrow_sub = subcolsplitrow.row(align=True)
        if current_km == default_km and self.IDPROP_NAME not in addon_prefs:
            subcolsplitrow_sub.enabled = False
        else:
            subcolsplitrow_sub.enabled = current_km != idp_km
        subcolsplitrow_sub.operator('wm.ari_keymaps_write', text='Write')
        # Restore
        subcolsplitrow_sub = subcolsplitrow.row(align=True)
        if current_km == default_km and self.IDPROP_NAME not in addon_prefs:
            subcolsplitrow_sub.enabled = False
        subcolsplitrow_sub.operator('wm.ari_keymaps_restore', text='Restore')

    def draw(self, context, layout=None, hierarchy=False, box=True):
        """キーマップアイテムの一覧を描画。
        :param context: _bpy.types.Context
        :param layout: _bpy.types.UILayout
        :param hierarchy: 階層表示にする
        :type hierarchy: bool
        :param box: 展開時にBoxで囲む
        :type box: bool
        """
        if not layout:
            layout = self.layout
        addon_prefs = self.get_instance()

        column = layout.column()
        column.context_pointer_set('addon_preferences', addon_prefs)

        wm_prop = self.__get_wm_prop()
        show_keymaps = wm_prop.show_keymaps
        show_classes = wm_prop.show_classes
        show_attributes = wm_prop.show_attributes

        row = column.row()
        split = row.split()

        sub = split.row()
        icon = 'TRIA_DOWN' if show_keymaps else 'TRIA_RIGHT'
        sub.prop(wm_prop, 'show_keymaps', text='', icon=icon, emboss=False)

        text = '{} Key Map Items'.format(len(self.keymap_items))
        sub.label(text)

        sub = split.row()
        icon = 'TRIA_DOWN' if show_classes else 'TRIA_RIGHT'
        sub.prop(wm_prop, 'show_classes', text='', icon=icon, emboss=False)
        text = '{} Classes'.format(len(self.addon_classes))
        sub.label(text)

        if self.addon_attributes:
            sub = split.row()
            icon = 'TRIA_DOWN' if show_attributes else 'TRIA_RIGHT'
            sub.prop(wm_prop, 'show_attributes', text='', icon=icon,
                     emboss=False)
            text = '{} Attributes'.format(len(self.addon_attributes))
            sub.label(text)

        if show_keymaps:
            self.__draw_keymaps(context, column, hierarchy, box)
        if show_classes and self.addon_classes:
            self.__draw_classes(context, layout, box)
        if show_attributes and self.addon_attributes:
            self.__draw_attributes(context, layout, box)

    # operator ------------------------------------------------------
    class _Helper:
        def get_addon_register_info(self, context):
            """
            :rtype: AddonRegisterInfo
            """
            addon_prefs = context.addon_preferences
            for attr in dir(addon_prefs.__class__):  # クラスにしか属性が無い
                obj = getattr(addon_prefs, attr)
                if hasattr(obj, 'ADDON_REGISTER_INFO'):
                    return obj
            raise ValueError()

    class _Registerable(_Helper):
        @classmethod
        def register_class(cls, rename=False):
            import re
            if issubclass(cls, _bpy.types.Operator):
                mod, func = cls.bl_idname.split('.')
                class_name = mod.upper() + '_OT_' + func
            elif issubclass(cls, _bpy.types.Menu):
                class_name = cls.bl_idname
            else:
                class_name = cls.__name__
            if rename:
                if cls._users == 0 or not hasattr(_bpy.types, class_name):
                    while hasattr(_bpy.types, class_name):
                        base, num = re.match('([a-zA-Z_]+)(\d*)$',
                                             func).groups()
                        if num == '':
                            func = base + '0'
                        else:
                            func = base + str(int(num) + 1)
                        class_name = mod.upper() + '_OT_' + func
                    cls.bl_idname = mod + '.' + func
                    _bpy.utils.register_class(cls)
                    cls._users = 1
                else:
                    print('{} already registered'.format(cls))
            else:
                if hasattr(_bpy.types, class_name):
                    getattr(_bpy.types, class_name)._users += 1
                else:
                    _bpy.utils.register_class(cls)
                    cls._users = 1

        @classmethod
        def unregister_class(cls, force=False):
            if issubclass(cls, _bpy.types.Operator):
                mod, func = cls.bl_idname.split('.')
                class_name = mod.upper() + '_OT_' + func
            elif issubclass(cls, _bpy.types.Menu):
                class_name = cls.bl_idname
            else:
                class_name = cls.__name__
            if hasattr(_bpy.types, class_name):
                other_cls = getattr(_bpy.types, class_name)
                if other_cls._users > 0:
                    other_cls._users -= 1
                if force:
                    other_cls._users = 0
                if other_cls._users == 0:
                    _bpy.utils.unregister_class(other_cls)
            else:
                _bpy.utils.unregister_class(cls)  # 例外を出させるため

    class _OperatorKeymapItemAdd(_Registerable, _bpy.types.Operator):
        bl_idname = 'wm.ari_keymap_item_add'
        bl_label = 'Add Key Map Item'
        bl_description = 'Add key map item'

        def _get_entries():
            import bpy_extras.keyconfig_utils

            modal_keymaps = {'View3D Gesture Circle', 'Gesture Border',
                             'Gesture Zoom Border', 'Gesture Straight Line',
                             'Standard Modal Map', 'Knife Tool Modal Map',
                             'Transform Modal Map', 'Paint Stroke Modal',
                             'View3D Fly Modal', 'View3D Walk Modal',
                             'View3D Rotate Modal', 'View3D Move Modal',
                             'View3D Zoom Modal', 'View3D Dolly Modal', }

            def get():
                def _get(entry):
                    idname, spaceid, regionid, children = entry
                    if not ('INVALID_MODAL_KEYMAP' and
                                idname in modal_keymaps):
                        yield entry
                        for e in children:
                            yield from _get(e)

                for entry in bpy_extras.keyconfig_utils.KM_HIERARCHY:
                    yield from _get(entry)

            return list(get())

        keymap = _bpy.props.EnumProperty(
            name='KeyMap',
            items=[(entry[0], entry[0], '') for entry in _get_entries()])

        def execute(self, context):
            ari = self.get_addon_register_info(context)
            km = ari.get_keymap(self.keymap)
            if km.is_modal:
                kmi = km.keymap_items.new_modal(
                    propvalue='', type='A', value='PRESS')
                print("WARNING: '{}' is modal keymap. "
                      "Cannot remove keymap item "
                      "when unregister".format(self.keymap))
            else:
                kmi = km.keymap_items.new(
                    idname='none', type='A', value='PRESS')
                ari.keymap_item_add(kmi)
            context.area.tag_redraw()
            return {'FINISHED'}

        def invoke(self, context, event):
            if self.properties.is_property_set('keymap'):
                return self.execute(context)
            else:
                return _bpy.ops.wm.call_menu(name='WM_MT_ari_keymap_item_add')

    class _OperatorKeymapItemRemove(_Registerable, _bpy.types.Operator):
        bl_idname = 'wm.ari_keymap_item_remove'
        bl_label = 'Remove Key Map Item'
        bl_description = 'Remove key map item'

        item_id = _bpy.props.IntProperty()

        def execute(self, context):
            ari = self.get_addon_register_info(context)
            for kmi in context.keymap.keymap_items:
                if kmi.id == self.item_id:
                    ari.keymap_item_remove(kmi)
                    return {'FINISHED'}
            context.area.tag_redraw()
            return {'CANCELLED'}

    class _OperatorKeymapsWrite(_Registerable, _bpy.types.Operator):
        bl_idname = 'wm.ari_keymaps_write'
        bl_label = 'Write KeyMaps'
        bl_description = 'Convert key map items into ID properties ' \
                         '(necessary for \'Save User Settings\')'

        def execute(self, context):
            addon_prefs = context.addon_preferences
            ari = self.get_addon_register_info(context)
            value = ari.keymap_items_get_attributes()
            addon_prefs[ari.IDPROP_NAME] = value
            return {'FINISHED'}

    class _OperatorKeymapsRestore(_Registerable, _bpy.types.Operator):
        bl_idname = 'wm.ari_keymaps_restore'
        bl_label = 'Restore KeyMaps'
        bl_description = 'Restore key map items and clear ID properties'

        def execute(self, context):
            addon_prefs = context.addon_preferences
            ari = self.get_addon_register_info(context)
            ari.keymap_items_restore()
            if ari.IDPROP_NAME in addon_prefs:
                del addon_prefs[ari.IDPROP_NAME]
            context.area.tag_redraw()
            return {'FINISHED'}

    # menu ----------------------------------------------------------
    class _MenuKeymapItemAdd(_Registerable, _bpy.types.Menu):
        bl_idname = 'WM_MT_ari_keymap_item_add'
        bl_label = 'Add New'

        def draw(self, context):
            import bpy_extras.keyconfig_utils

            addon_prefs = context.addon_preferences
            ari = self.get_addon_register_info(context)

            layout = self.layout
            column = layout.column()
            column.context_pointer_set('addon_preferences', addon_prefs)

            def get_non_modal_km_hierarchy():
                if not 'INVALID_MODAL_KEYMAP':
                    return bpy_extras.keyconfig_utils.KM_HIERARCHY

                modal_keymaps = {'View3D Gesture Circle', 'Gesture Border',
                                 'Gesture Zoom Border',
                                 'Gesture Straight Line', 'Standard Modal Map',
                                 'Knife Tool Modal Map', 'Transform Modal Map',
                                 'Paint Stroke Modal', 'View3D Fly Modal',
                                 'View3D Walk Modal', 'View3D Rotate Modal',
                                 'View3D Move Modal', 'View3D Zoom Modal',
                                 'View3D Dolly Modal'}

                def get_entry(entry):
                    idname, spaceid, regionid, children = entry
                    if idname not in modal_keymaps:
                        children_non_modal = []
                        for child in children:
                            e = get_entry(child)
                            if e:
                                children_non_modal.append(e)
                        return [idname, spaceid, regionid, children_non_modal]

                km_hierarchy = [e for e in
                                [get_entry(e) for e in
                                 bpy_extras.keyconfig_utils.KM_HIERARCHY]
                                if e]
                return km_hierarchy

            km_hierarchy = get_non_modal_km_hierarchy()

            def max_depth(entry, depth):
                idname, spaceid, regionid, children = entry
                if children:
                    d = max([max_depth(e, depth + 1) for e in children])
                    return max(depth, d)
                else:
                    return depth
            depth = 1
            for entry in bpy_extras.keyconfig_utils.KM_HIERARCHY:
                depth = max(depth, max_depth(entry, 1))

            used_keymap_names = {kmname for kmname, kmiid in ari.keymap_items}

            # 左の列を全部描画してから右の列にいかないとおかしな事になる

            table = []
            def gen_table(entry, row_index, col_index):
                idname, spaceid, regionid, children = entry
                if row_index > len(table) - 1:
                    table.append([None for i in range(depth)])
                table[row_index][col_index] = idname
                if children:
                    col_index += 1
                    for e in children:
                        row_index = gen_table(e, row_index, col_index)
                else:
                    row_index += 1
                return row_index
            row_index = 0
            col_index = 0
            for entry in km_hierarchy:
                row_index = gen_table(entry, row_index, col_index)

            split_list = []
            for i, row in enumerate(table):
                if row[0] and i > 0:
                    split_list.append((column.split(), False))
                split_list.append((column.split(), True))
            for i in range(depth):
                j = 0
                for split, not_separator in split_list:
                    row = split.row()
                    if not_separator:
                        name = table[j][i]
                        if name:
                            if name in used_keymap_names:
                                icon = 'FILE_TICK'
                            else:
                                icon = 'NONE'
                            op = row.operator('wm.ari_keymap_item_add',
                                              text=name, icon=icon)
                            op.keymap = name
                        j += 1
                    else:
                        row.separator()

    # property ------------------------------------------------------
    class _AddonRegisterInformation(_Registerable, _bpy.types.PropertyGroup):
        """WindowManager.addon_register_information"""
        pass

    _AddonRegisterInformation.__name__ = 'AddonRegisterInformation'

    class _AddonRegisterInformationUI(_Registerable, _bpy.types.PropertyGroup):
        """AddonRegisterInformationの属性"""
        show_keymaps = _bpy.props.BoolProperty(
            name='Show KeyMaps',
        )
        filter_type = _bpy.props.EnumProperty(
            name='Filter Type',
            description='Filter method',
            items=[('NAME', 'Name',
                    'Filter based on the operator name'),
                   ('KEY', 'Key-Binding',
                    'Filter based on key bindings')],
            default='NAME',
        )
        filter_text = _bpy.props.StringProperty(
            name='Filter',
            description='Search term for filtering in the UI',
        )
        show_classes = _bpy.props.BoolProperty(
            name='Show Classes',
        )
        show_attributes = _bpy.props.BoolProperty(
            name='Show Attributes',
        )

    _AddonRegisterInformationUI.__name__ = 'AddonRegisterInformationUI'

    # wrap ----------------------------------------------------------
    @classmethod
    def module_register(cls, func, instance=None):
        import functools

        def get_km_items():
            kc = _bpy.context.window_manager.keyconfigs.addon
            if not kc:
                return None

            items = []
            for km in kc.keymaps:
                for kmi in km.keymap_items:
                    items.append((km, kmi))
            return items

        @functools.wraps(func)
        def _register():
            items_pre = get_km_items()
            bpy_types_pre = set(dir(_bpy.types))

            func()

            items_post = get_km_items()
            bpy_types_post = set(dir(_bpy.types))

            if items_pre is not None and items_post is not None:
                keymap_items = [item for item in items_post
                                if item not in items_pre]
            else:
                keymap_items = []

            new_type_names = []
            addon_prefs_class = None
            for attr in bpy_types_post:
                if attr in bpy_types_pre:
                    continue
                new_type_names.append(attr)
                c = getattr(_bpy.types, attr)
                if issubclass(c, _bpy.types.AddonPreferences):
                    addon_prefs_class = c

            if instance:  # addon_utils.py用
                instance.register()

                draw_orig = None
                if addon_prefs_class:
                    if hasattr(addon_prefs_class, 'draw'):
                        def draw(self, context):
                            draw._draw(self, context)
                            instance.draw(context, layout=self.layout)

                        draw_orig = addon_prefs_class.draw
                    else:
                        def draw(self, context):
                            instance.draw(context, layout=self.layout)
                    addon_prefs_class.draw = draw

                else:
                    def draw(self, context):
                        instance.draw(context, layout=self.layout)

                    cls_ = instance.__class__
                    name = cls_.bl_idname.replace('.', '_').upper()
                    addon_prefs_class = type(
                        'AddonPreferences' + name,
                        (_bpy.types.AddonPreferences,),
                        {'bl_idname': instance.bl_idname,
                         'register_info': instance,
                         'draw': draw,
                         'is_temporary_class': True}
                    )
                    _bpy.utils.register_class(addon_prefs_class)
                draw._draw = draw_orig

                instance.__class__.addon_preferences_class = \
                    addon_prefs_class

            prop = _bpy.props.PointerProperty(
                type=_bpy.types.AddonRegisterInformationUI)
            setattr(_bpy.types.AddonRegisterInformation,
                    cls.bl_idname.replace('.', '_'), prop)

            if instance:
                instance.keymap_items_add(keymap_items)
                instance.addon_classes_add(new_type_names)
            else:
                cls.keymap_items_add(keymap_items)
                cls.addon_classes_add(new_type_names)

        _register._register = func

        return _register

    @classmethod
    def module_register_ex(cls, register_info=None):
        import functools
        return functools.partial(cls.module_register,
                                 register_info=register_info)

    @classmethod
    def module_unregister(cls, func, unregister_classes=False,
                          instance=None):
        import functools

        @functools.wraps(func)
        def _unregister():
            if instance:
                prefs_class = instance.__class__.addon_preferences_class
            else:
                prefs_class = cls

            delattr(_bpy.types.AddonRegisterInformation,
                    prefs_class.bl_idname.replace('.', '_'))

            if instance:
                instance.keymap_items_remove(remove_only_added=True)
                if unregister_classes:
                    instance.addon_classes_remove()
                else:
                    instance.addon_classes.clear()
            else:
                prefs_class.keymap_items_remove()
                if unregister_classes:
                    prefs_class.addon_classes_remove()
                else:
                    prefs_class.addon_classes.clear()

            if instance:
                if getattr(prefs_class, 'is_temporary_class', None) is True:
                    _bpy.utils.unregister_class(prefs_class)
                else:
                    if prefs_class.draw._draw:
                        prefs_class.draw = prefs_class.draw._draw
                    else:
                        delattr(prefs_class, 'draw')

                instance.unregister()

            func()

        _unregister._unregister = func
        return _unregister

    @classmethod
    def module_usregister_ex(cls, unregister_classes=False,
                             instance=None):
        import functools
        return functools.partial(cls.module_unregister,
                                 unregister_classes=unregister_classes,
                                 instance=instance)

    @classmethod
    def wrap_module(cls, module):
        """addon_utils.py用"""
        if getattr(module, 'bl_info', {}).get('name') in cls.IGRORE_ADDONS:
            return
        if not (hasattr(module, 'register') and hasattr(module, 'unregister')):
            return
        if hasattr(module.register, '_register'):
            return

        new_cls = cls.derive(module.__name__, lock_default_keymap_items=True)
        instance = new_cls()
        module.register = new_cls.module_register(module.register,
                                                  instance=instance)
        module.unregister = new_cls.module_unregister(module.unregister,
                                                      instance=instance)


# called only once at startup, avoids calling 'reset_all', correct but slower.
def _initialize():
    path_list = paths()
    for path in path_list:
        _bpy.utils._sys_path_ensure(path)
    for addon in _user_preferences.addons:
        enable(addon.module)


def paths():
    # RELEASE SCRIPTS: official scripts distributed in Blender releases
    addon_paths = _bpy.utils.script_paths("addons")

    # CONTRIB SCRIPTS: good for testing but not official scripts yet
    # if folder addons_contrib/ exists, scripts in there will be loaded too
    addon_paths += _bpy.utils.script_paths("addons_contrib")

    return addon_paths


def modules_refresh(module_cache=addons_fake_modules):
    global error_duplicates
    global error_encoding
    import os

    error_duplicates = False
    error_encoding = False

    path_list = paths()

    # fake module importing
    def fake_module(mod_name, mod_path, speedy=True, force_support=None):
        global error_encoding

        if _bpy.app.debug_python:
            print("fake_module", mod_path, mod_name)
        import ast
        ModuleType = type(ast)
        try:
            file_mod = open(mod_path, "r", encoding='UTF-8')
        except OSError as e:
            print("Error opening file %r: %s" % (mod_path, e))
            return None

        with file_mod:
            if speedy:
                lines = []
                line_iter = iter(file_mod)
                l = ""
                while not l.startswith("bl_info"):
                    try:
                        l = line_iter.readline()
                    except UnicodeDecodeError as e:
                        if not error_encoding:
                            error_encoding = True
                            print("Error reading file as UTF-8:", mod_path, e)
                        return None

                    if len(l) == 0:
                        break
                while l.rstrip():
                    lines.append(l)
                    try:
                        l = line_iter.readline()
                    except UnicodeDecodeError as e:
                        if not error_encoding:
                            error_encoding = True
                            print("Error reading file as UTF-8:", mod_path, e)
                        return None

                data = "".join(lines)

            else:
                data = file_mod.read()
        del file_mod

        try:
            ast_data = ast.parse(data, filename=mod_path)
        except:
            print("Syntax error 'ast.parse' can't read %r" % mod_path)
            import traceback
            traceback.print_exc()
            ast_data = None

        body_info = None

        if ast_data:
            for body in ast_data.body:
                if body.__class__ == ast.Assign:
                    if len(body.targets) == 1:
                        if getattr(body.targets[0], "id", "") == "bl_info":
                            body_info = body
                            break

        if body_info:
            try:
                mod = ModuleType(mod_name)
                mod.bl_info = ast.literal_eval(body.value)
                mod.__file__ = mod_path
                mod.__time__ = os.path.getmtime(mod_path)
            except:
                print("AST error parsing bl_info for %s" % mod_name)
                import traceback
                traceback.print_exc()
                raise

            if force_support is not None:
                mod.bl_info["support"] = force_support

            return mod
        else:
            print("fake_module: addon missing 'bl_info' "
                  "gives bad performance!: %r" % mod_path)
            return None

    modules_stale = set(module_cache.keys())

    for path in path_list:

        # force all contrib addons to be 'TESTING'
        if path.endswith(("addons_contrib", )):
            force_support = 'TESTING'
        else:
            force_support = None

        for mod_name, mod_path in _bpy.path.module_names(path):
            modules_stale.discard(mod_name)
            mod = module_cache.get(mod_name)
            if mod:
                if mod.__file__ != mod_path:
                    print("multiple addons with the same name:\n  %r\n  %r" %
                          (mod.__file__, mod_path))
                    error_duplicates = True

                elif mod.__time__ != os.path.getmtime(mod_path):
                    print("reloading addon:",
                          mod_name,
                          mod.__time__,
                          os.path.getmtime(mod_path),
                          mod_path,
                          )
                    del module_cache[mod_name]
                    mod = None

            if mod is None:
                mod = fake_module(mod_name,
                                  mod_path,
                                  force_support=force_support)
                if mod:
                    module_cache[mod_name] = mod

    # just in case we get stale modules, not likely
    for mod_stale in modules_stale:
        del module_cache[mod_stale]
    del modules_stale


def modules(module_cache=addons_fake_modules, *, refresh=True):
    if refresh or ((module_cache is addons_fake_modules) and modules._is_first):
        modules_refresh(module_cache)
        modules._is_first = False

    mod_list = list(module_cache.values())
    mod_list.sort(key=lambda mod: (mod.bl_info["category"],
                                   mod.bl_info["name"],
                                   ))
    return mod_list
modules._is_first = True


def check(module_name):
    """
    Returns the loaded state of the addon.

    :arg module_name: The name of the addon and module.
    :type module_name: string
    :return: (loaded_default, loaded_state)
    :rtype: tuple of booleans
    """
    import sys
    loaded_default = module_name in _user_preferences.addons

    mod = sys.modules.get(module_name)
    loaded_state = ((mod is not None) and
                    getattr(mod, "__addon_enabled__", Ellipsis))

    if loaded_state is Ellipsis:
        print("Warning: addon-module %r found module "
              "but without __addon_enabled__ field, "
              "possible name collision from file: %r" %
              (module_name, getattr(mod, "__file__", "<unknown>")))

        loaded_state = False

    if mod and getattr(mod, "__addon_persistent__", False):
        loaded_default = True

    return loaded_default, loaded_state

# utility functions


def _addon_ensure(module_name):
    addons = _user_preferences.addons
    addon = addons.get(module_name)
    if not addon:
        addon = addons.new()
        addon.module = module_name


def _addon_remove(module_name):
    addons = _user_preferences.addons

    while module_name in addons:
        addon = addons.get(module_name)
        if addon:
            addons.remove(addon)


def enable(module_name, *, default_set=False, persistent=False, handle_error=None):
    """
    Enables an addon by name.

    :arg module_name: the name of the addon and module.
    :type module_name: string
    :arg default_set: Set the user-preference.
    :type default_set: bool
    :arg persistent: Ensure the addon is enabled for the entire session (after loading new files).
    :type persistent: bool
    :arg handle_error: Called in the case of an error, taking an exception argument.
    :type handle_error: function
    :return: the loaded module or None on failure.
    :rtype: module
    """

    import os
    import sys
    from bpy_restrict_state import RestrictBlend

    if handle_error is None:
        def handle_error(ex):
            import traceback
            traceback.print_exc()

    # reload if the mtime changes
    mod = sys.modules.get(module_name)
    # chances of the file _not_ existing are low, but it could be removed
    if mod and os.path.exists(mod.__file__):

        if getattr(mod, "__addon_enabled__", False):
            # This is an unlikely situation,
            # re-register if the module is enabled.
            # Note: the UI doesn't allow this to happen,
            # in most cases the caller should 'check()' first.
            try:
                mod.unregister()
            except Exception as ex:
                print("Exception in module unregister(): %r" %
                      getattr(mod, "__file__", module_name))
                handle_error(ex)
                return None

        mod.__addon_enabled__ = False
        mtime_orig = getattr(mod, "__time__", 0)
        mtime_new = os.path.getmtime(mod.__file__)
        if mtime_orig != mtime_new:
            import importlib
            print("module changed on disk:", mod.__file__, "reloading...")

            try:
                importlib.reload(mod)
            except Exception as ex:
                handle_error(ex)
                del sys.modules[module_name]
                return None
            mod.__addon_enabled__ = False

    # add the addon first it may want to initialize its own preferences.
    # must remove on fail through.
    if default_set:
        _addon_ensure(module_name)

    # Split registering up into 3 steps so we can undo
    # if it fails par way through.

    # disable the context, using the context at all is
    # really bad while loading an addon, don't do it!
    with RestrictBlend():

        # 1) try import
        try:
            mod = __import__(module_name)
            mod.__time__ = os.path.getmtime(mod.__file__)
            mod.__addon_enabled__ = False
        except Exception as ex:
            # if the addon doesn't exist, dont print full traceback
            if type(ex) is ImportError and ex.name == module_name:
                print("addon not found: %r" % module_name)
            else:
                handle_error(ex)

            if default_set:
                _addon_remove(module_name)
            return None

        # 2) try register collected modules
        # removed, addons need to handle own registration now.

        # 3) try run the modules register function
        try:
            AddonRegisterInfo.wrap_module(mod)
            mod.register()
        except Exception as ex:
            print("Exception in module register(): %r" %
                  getattr(mod, "__file__", module_name))
            handle_error(ex)
            del sys.modules[module_name]
            if default_set:
                _addon_remove(module_name)
            return None

    # * OK loaded successfully! *
    mod.__addon_enabled__ = True
    mod.__addon_persistent__ = persistent

    if _bpy.app.debug_python:
        print("\taddon_utils.enable", mod.__name__)

    return mod


def disable(module_name, *, default_set=False, handle_error=None):
    """
    Disables an addon by name.

    :arg module_name: The name of the addon and module.
    :type module_name: string
    :arg default_set: Set the user-preference.
    :type default_set: bool
    :arg handle_error: Called in the case of an error, taking an exception argument.
    :type handle_error: function
    """
    import sys

    if handle_error is None:
        def handle_error(ex):
            import traceback
            traceback.print_exc()

    mod = sys.modules.get(module_name)

    # possible this addon is from a previous session and didn't load a
    # module this time. So even if the module is not found, still disable
    # the addon in the user prefs.
    if mod and getattr(mod, "__addon_enabled__", False) is not False:
        mod.__addon_enabled__ = False
        mod.__addon_persistent = False

        try:
            mod.unregister()
        except Exception as ex:
            print("Exception in module unregister(): %r" %
                  getattr(mod, "__file__", module_name))
            handle_error(ex)
    else:
        print("addon_utils.disable: %s not %s." %
              (module_name, "disabled" if mod is None else "loaded"))

    # could be in more than once, unlikely but better do this just in case.
    if default_set:
        _addon_remove(module_name)

    if _bpy.app.debug_python:
        print("\taddon_utils.disable", module_name)


def reset_all(*, reload_scripts=False):
    """
    Sets the addon state based on the user preferences.
    """
    import sys

    # initializes addons_fake_modules
    modules_refresh()

    # RELEASE SCRIPTS: official scripts distributed in Blender releases
    paths_list = paths()

    for path in paths_list:
        _bpy.utils._sys_path_ensure(path)
        for mod_name, mod_path in _bpy.path.module_names(path):
            is_enabled, is_loaded = check(mod_name)

            # first check if reload is needed before changing state.
            if reload_scripts:
                import importlib
                mod = sys.modules.get(mod_name)
                if mod:
                    importlib.reload(mod)
                    AddonRegisterInfo.wrap_module(mod)

            if is_enabled == is_loaded:
                pass
            elif is_enabled:
                enable(mod_name)
            elif is_loaded:
                print("\taddon_utils.reset_all unloading", mod_name)
                disable(mod_name)


def module_bl_info(mod, info_basis=None):
    if info_basis is None:
        info_basis = {
            "name": "",
            "author": "",
            "version": (),
            "blender": (),
            "location": "",
            "description": "",
            "wiki_url": "",
            "support": 'COMMUNITY',
            "category": "",
            "warning": "",
            "show_expanded": False,
        }

    addon_info = getattr(mod, "bl_info", {})

    # avoid re-initializing
    if "_init" in addon_info:
        return addon_info

    if not addon_info:
        mod.bl_info = addon_info

    for key, value in info_basis.items():
        addon_info.setdefault(key, value)

    if not addon_info["name"]:
        addon_info["name"] = mod.__name__

    addon_info["_init"] = None
    return addon_info
