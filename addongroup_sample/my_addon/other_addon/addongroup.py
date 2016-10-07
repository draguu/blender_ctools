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


"""
アドオンの階層構造を作る為のモジュール。

使い方。
この様なファイル構造を例とする。
2.78/scripts/addons/my_addon/ --- __init__.py
                               |- addongroup.py
                               |- foo.py
                               |
                               |- child_addon/ --- __init__.py
                               |                |- addongroup.py
                               |                `- bar.py
                               |
                               `- other_addon/ --- __init__.py
                                                `- addongroup.py

### my_addon/__init__.py ###

bl_info = {
    'name': 'My Addon',
    'version': (0, 1),
    'category': 'User Interface',
}

if 'bpy' in locals():  # F8キーでモジュールが再読み込みされる場合。
    import importlib
    importlib.reload(addongroup)
    importlib.reload(foo)
    MyAddonPreferences.reload_sub_modules()  # 子のアドオンを再読み込み。
else:
    from . import addongroup
    from . import foo

import bpy

class MyAddonPreferences(
        addongroup.AddonGroupPreferences,
        bpy.types.AddonPreferences if '.' not in __name__ else
        bpy.types.PropertyGroup):

    bl_idname = __name__

    # 対象のアドオンを指定。
    sub_modules = [
        'child_addon',
        'other_addon',
    ]

    def draw(self, context):
        ...
        # AddonGroupPreferencesのdrawメソッドで子のアドオンの設定を表示する。
        super().draw(context)

    @classmethod
    def register(cls):
        ...
        # registerやunregisterクラスメソッドを定義するなら
        # addongrouppreferencesのメソッドも呼んでおくこと。
        super().register()

    @classmethod
    def unregister(cls):
        ...
        super().unregister()

classes = [
    MyAddonPreferences,
    ...
]

def register():
    # AddonGroupPreferencesが依存するクラスがあるので、
    # それを先に登録する必要がある。
    MyAddonPreferences.ensure_register()

    for cls in classes:
        bpy.utils.register_class(cls)

    # prefs = bpy.context.user_preferences.addons[__name__].preferences
    # 普通はこのやり方でアドオンの設定を参照出来るけど、入れ子にした場合は
    # この方法は使えないので代わりにget_instanceクラスメソッドを使う。
    # これはアドオンを入れ子にしていない場合でも使える。
    prefs = MyAddonPreferences.get_instance()

    # UserPreferences画面で詳細が表示されているかはshow_expanded_+モジュール名の属性。
    show_other_addon_detail = prefs.show_expanded_other_addon

    # アドオンが有効か否かは use_ + モジュール名。
    if prefs.use_child_addon:
        # 子のアドオンの設定はモジュール名。
        child_addon_prefs = prefs.child_addon
    if prefs.use_other_addon:
        other_addon_prefs = prefs.other_addon

def unregister():
    for cls in classes[::-1]:
        bpy.utils.unregister_class(cls)


### my_addon/child_addon/__init__.py ###
### my_addon/other_addon/__init__.py ###

# my_addon/__init__.py と基本的な書き方は一緒。

if 'bpy' in locals():
    import importlib
    importlib.reload(addongroup)
    importlib.reload(bar)
    # MyAddonChildPreferences.reload_sub_modules()  # 子は無いので不要。
else:
    from . import addongroup
    from . import bar

import bpy

# もし、元々アドオンにAddonPreferencesが定義されてなくて、子のアドオンも
# 無いのなら、新たに定義する必要は無い。
class MyAddonChildPreferences(
        addongroup.AddonGroupPreferences,
        bpy.types.AddonPreferences if '.' not in __name__ else
        bpy.types.PropertyGroup):

    bl_idname = __name__

    sub_modules = []

(以下略)

"""


from collections import OrderedDict
import importlib
import os
import re
import sys
import traceback

import bpy


class AddonGroupPreferencesMiscellaneous(bpy.types.PropertyGroup):
    """bpy.types.AddonPreferencesを継承したクラスへ動的に属性を追加しても
    インスタンスへは反映されない為、代わりにこれへ属性を追加する。
    """
    _users = 0


class AddonGroupPreferences:
    """入れ子のアドオンを作る為のもの。
    AddonPreferencesのクラスを作る際にこれも継承する。
    """

    # この二つの属性は継承したクラスで上書きする
    bl_idname = ''
    sub_modules = []
    """:type: list[str]"""

    # 末尾の _ は念の為に他と名前が被らないよう加えたもの
    # TODO: misc_ とかに名前を変える？
    misc_ = bpy.props.PointerProperty(
        type=AddonGroupPreferencesMiscellaneous)

    _fake_sub_modules = OrderedDict()

    @classmethod
    def _get_misc_type(cls):
        return cls.misc_[1]['type']

    @classmethod
    def ensure_register(cls):
        """このクラスはAddonGroupPreferencesMiscellaneousに依存するので
        bpy.utils.register_class()の前に必ず実行しておく事。
        rootのアドオンで一度だけやっておけばいい。
        """
        misc_type = cls._get_misc_type()
        if not misc_type.is_registered:
            bpy.utils.register_class(misc_type)

    @classmethod
    def reload_sub_modules(cls):
        for fake_mod in cls._gen_fake_sub_modules().values():
            try:
                if fake_mod.__name__ in sys.modules:
                    mod = importlib.import_module(fake_mod.__name__)
                    importlib.reload(mod)
            except:
                traceback.print_exc()

    @classmethod
    def get_instance(cls):
        """AddonPreferencesのインスタンスを返す。
        :rtype: AddonPreferences
        """
        U = bpy.context.user_preferences
        attrs = cls.bl_idname.split('.')
        if attrs[0] not in U.addons:  # wm.read_factory_settings()
            return None
        prefs = U.addons[attrs[0]].preferences
        for attr in attrs[1:]:
            if not hasattr(prefs, attr):
                return None
            prefs = getattr(prefs, attr)
        return prefs

    @staticmethod
    def _replace_dot(name):
        return name.replace('.', '__')

    @classmethod
    def _fake_module(cls, mod_name, mod_path, speedy=True, force_support=None):
        """scripts/modules/addon_utils.pyのmodule_refresh関数の中からコピペして
        error_encodingを使わないように修正したもの。
        """
        if 0:
            global error_encoding

        if bpy.app.debug_python:
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
                        if 0:
                            if not error_encoding:
                                error_encoding = True
                                print("Error reading file as UTF-8:", mod_path,
                                      e)
                        else:
                            print("Error reading file as UTF-8:", mod_path, e)
                        return None

                    if len(l) == 0:
                        break
                while l.rstrip():
                    lines.append(l)
                    try:
                        l = line_iter.readline()
                    except UnicodeDecodeError as e:
                        if 0:
                            if not error_encoding:
                                error_encoding = True
                                print("Error reading file as UTF-8:", mod_path,
                                      e)
                        else:
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

    @classmethod
    def _gen_fake_sub_modules(cls):
        # cls._face_modulesの生成
        fake_modules = []
        mod = sys.modules[cls.__module__]
        curdir = os.path.dirname(mod.__file__)
        files = os.listdir(curdir)
        for name in cls.sub_modules:
            if name in files:  # directory
                p = os.path.join(curdir, name, '__init__.py')
            else:  # .py
                p = os.path.join(curdir, name + '.py')
            mod = cls._fake_module(cls.__module__ + '.' + name, p)
            if mod:
                fake_modules.append(mod)
        fake_modules.sort(
            key=lambda mod: (mod.bl_info['category'], mod.bl_info['name']))
        return OrderedDict([(mod.__name__.split('.')[-1], mod)
                            for mod in fake_modules])

    @classmethod
    def _init_fake_sub_modules(cls):
        cls._fake_sub_modules = cls._gen_fake_sub_modules()

    @classmethod
    def _init_attributes(cls):
        prefs = cls.get_instance()
        misc_type = cls._get_misc_type()

        for name, fake_mod in cls._fake_sub_modules.items():
            info = fake_mod.bl_info

            def gen_update(fake_mod):
                def update(self, context):
                    name_attr = cls._replace_dot(fake_mod.__name__)
                    try:
                        mod = importlib.import_module(fake_mod.__name__)
                        if getattr(self, 'use_' + name_attr):
                            cls._register_sub_module(mod)
                        else:
                            cls._unregister_sub_module(mod, True)
                    except:
                        traceback.print_exc()
                return update

            prop = bpy.props.BoolProperty(
                name=info['name'],
                description=info.get('description', '').rstrip('.'),
                update=gen_update(fake_mod),
            )
            setattr(prefs, 'use_' + name, prop)

            def gen_func(fake_mod):
                attr = cls._replace_dot(fake_mod.__name__)
                def fget(self):
                    return getattr(misc_type, '_show_expanded_' + attr, False)
                def fset(self, value):
                    setattr(misc_type, '_show_expanded_' + attr, value)
                return fget, fset
            fget, fset = gen_func(fake_mod)
            prop = bpy.props.BoolProperty(get=fget, set=fset)
            setattr(prefs, 'show_expanded_' + name, prop)

    @classmethod
    def _register_sub_module(cls, mod):
        if not hasattr(mod, '__addon_enabled__'):
            mod.__addon_enabled__ = False
        if not mod.__addon_enabled__:
            mod.register()
            mod.__addon_enabled__ = True

    @classmethod
    def _unregister_sub_module(cls, mod, clear_preferences=False):
        if not hasattr(mod, '__addon_enabled__'):
            mod.__addon_enabled__ = False
        if mod.__addon_enabled__:
            mod.unregister()
            mod.__addon_enabled__ = False

        if clear_preferences:
            prefs = cls.get_instance()
            for prefix in ('', 'use_', 'show_expanded_'):
                attr = prefix + cls._replace_dot(mod.__name__)
                if attr in prefs.misc_:
                    del prefs.misc_[attr]

    @classmethod
    def register(cls):
        # 親オブジェクトへの登録。_init_attributes()でget_instance()を
        # 使うので先に処理しておく
        if '.' in cls.bl_idname:
            U = bpy.context.user_preferences
            attrs = cls.bl_idname.split('.')
            base_prop = U.addons[attrs[0]].preferences
            for attr in attrs[1:-1]:
                base_prop = getattr(base_prop, attr)
            prop = bpy.props.PointerProperty(type=cls)
            setattr(base_prop, attrs[-1], prop)

        cls._init_fake_sub_modules()
        cls._init_attributes()

        # register sub modules
        prefs = cls.get_instance()
        for name, fake_mod in cls._fake_sub_modules.items():
            if getattr(prefs, 'use_' + name):
                try:
                    mod = importlib.import_module(fake_mod.__name__)
                    cls._register_sub_module(mod)
                except:
                    setattr(prefs, 'use_' + name, False)
                    traceback.print_exc()

        c = super()
        if hasattr(c, 'register'):
            c.register()

        misc_type = cls._get_misc_type()
        misc_type._users += 1

    @classmethod
    def unregister(cls):
        # unregister sub modules
        U = bpy.context.user_preferences
        if __name__ in U.addons:  # wm.read_factory_settings()の際に偽となる
            return

        prefs = cls.get_instance()
        misc_type = cls._get_misc_type()
        for name, fake_mod in cls._fake_sub_modules.items():
            if getattr(prefs, 'use_' + name):
                try:
                    mod = importlib.import_module(fake_mod.__name__)
                    cls._unregister_sub_module(mod)
                except:
                    traceback.print_exc()
            delattr(prefs, 'use_' + name)
            delattr(prefs, 'show_expanded_' + name)
            attr = cls._replace_dot(fake_mod.__name__)
            if hasattr(misc_type, '_show_expanded_' + attr):
                delattr(misc_type, '_show_expanded_' + attr)

        cls._fake_sub_modules.clear()

        if '.' in cls.bl_idname:
            # 親オブジェクトからの登録解除。
            # ctools以外での使用を想定していない
            attrs = cls.bl_idname.split('.')
            base_prop = U.addons[attrs[0]].preferences
            for attr in attrs[1:-1]:
                base_prop = getattr(base_prop, attr)
            delattr(base_prop, attrs[-1])

        c = super()
        if hasattr(c, 'unregister'):
            c.unregister()

        misc_type = cls._get_misc_type()
        misc_type._users -= 1
        if misc_type._users == 0:
            bpy.utils.unregister_class(misc_type)

    def __getattribute__(self, name):
        prefix, base = re.match('(use_|show_expanded_|)(.*)', name).groups()
        if base in super().__getattribute__('_fake_sub_modules'):
            p = super().__getattribute__('misc_')
            attr = prefix + self._replace_dot(
                self._fake_sub_modules[base].__name__)
            return getattr(p, attr)
        else:
            return super().__getattribute__(name)

    def __setattr__(self, name, value):
        def is_bpy_props(val):
            """valueが (bpy.props.BoolProperty, {name='Name', default='True'})
            といった形式の場合に真を返す。
            """
            try:
                t, kwargs = val
                props = [getattr(bpy.props, attr) for attr in dir(bpy.props)]
                return t in props and isinstance(kwargs, dict)
            except:
                return False

        prefix, base = re.match('(use_|show_expanded_|)(.*)', name).groups()
        if base in self._fake_sub_modules:
            p = self.misc_
            attr = prefix + self._replace_dot(
                self._fake_sub_modules[base].__name__)
            if is_bpy_props(value):
                setattr(p.__class__, attr, value)
            else:
                setattr(p, attr, value)
        else:
            super().__setattr__(name, value)

    def __delattr__(self, name):
        prefix, base = re.match('(use_|show_expanded_|)(.*)', name).groups()
        if base in self._fake_sub_modules:
            p = self.misc_
            attr = prefix + self._replace_dot(
                self._fake_sub_modules[base].__name__)
            delattr(p.__class__, attr)
        else:
            super().__delattr__(name)

    def __dir__(self):
        attrs = list(super().__dir__())
        p = self.misc_
        print('__dir__ >>', dir(p))
        for name in self._fake_sub_modules:
            attr = self._replace_dot(self._fake_sub_modules[name].__name__)
            for pre in ('', 'use_', 'show_expanded_'):
                n = pre + attr
                if hasattr(p, n):
                    attrs.append(pre + name)
        return attrs

    align_box_draw_ = bpy.props.BoolProperty(
        name='Box Draw',
        description='If applied patch: patch/ui_layout_box.patch',
        default=False)
    use_indent_draw_ = bpy.props.BoolProperty(
        name='Indent',
        default=True)

    def draw(self, context):
        layout = self.layout
        """:type: bpy.types.UILayout"""

        bl_idname = self.__class__.bl_idname

        if '.' not in bl_idname:
            align_box_draw = self.align_box_draw_
            use_indent_draw = self.use_indent_draw_
        else:
            U = context.user_preferences
            root_prefs = U.addons[bl_idname.split('.')[0]].preferences
            align_box_draw = root_prefs.align_box_draw_
            use_indent_draw = root_prefs.use_indent_draw_

        for mod_name, fake_mod in self._fake_sub_modules.items():
            mod_name_attr = self._replace_dot(fake_mod.__name__)
            info = fake_mod.bl_info
            column = layout.column(align=align_box_draw)

            # インデント
            if use_indent_draw:
                sp = column.split(0.01)
                sp.column()
                column = sp.column(align=align_box_draw)

            box = column.box()

            # 一段目
            expand = getattr(self, 'show_expanded_' + mod_name)
            icon = 'TRIA_DOWN' if expand else 'TRIA_RIGHT'
            col = box.column()  # boxのままだと行間が広い
            row = col.row()
            sub = row.row()
            sub.context_pointer_set('addon_prefs', self)
            sub.alignment = 'LEFT'
            op = sub.operator('wm.context_toggle', text='', icon=icon,
                              emboss=False)
            op.data_path = 'addon_prefs.show_expanded_' + mod_name
            sub.label('{}: {}'.format(info['category'], info['name']))
            sub = row.row()
            sub.alignment = 'RIGHT'
            if info.get('warning'):
                sub.label('', icon='ERROR')
            sub.prop(self.misc_, 'use_' + mod_name_attr, text='')
            # 二段目
            if expand:
                # col = box.column()  # boxのままだと行間が広い
                # 参考: space_userpref.py
                if info.get('description'):
                    split = col.row().split(percentage=0.15)
                    split.label('Description:')
                    split.label(info['description'])
                if info.get('location'):
                    split = col.row().split(percentage=0.15)
                    split.label('Location:')
                    split.label(info['location'])
                split = col.row().split(percentage=0.15)
                split.label('File:')
                split.label(fake_mod.__file__)
                if info.get('author'):
                    mod = sys.modules[bl_idname]
                    base_info = getattr(mod, 'bl_info', None)
                    if not isinstance(base_info, dict):
                        base_info = {}
                    if info['author'] != base_info.get('author'):
                        split = col.row().split(percentage=0.15)
                        split.label('Author:')
                        split.label(info['author'])
                if info.get('version'):
                    split = col.row().split(percentage=0.15)
                    split.label('Version:')
                    split.label('.'.join(str(x) for x in info['version']),
                                translate=False)
                if info.get('warning'):
                    split = col.row().split(percentage=0.15)
                    split.label('Warning:')
                    split.label('  ' + info['warning'], icon='ERROR')

                tot_row = int(bool(info.get('wiki_url')))
                if tot_row:
                    split = col.row().split(percentage=0.15)
                    split.label(text='Internet:')
                    if info.get('wiki_url'):
                        op = split.operator('wm.url_open',
                                            text='Documentation', icon='HELP')
                        op.url = info.get('wiki_url')
                    for i in range(4 - tot_row):
                        split.separator()

                # 詳細・設定値
                if getattr(self, 'use_' + mod_name):
                    try:
                        prefs = getattr(self, mod_name, None)
                    except:
                        traceback.print_exc()
                        continue
                    if prefs and hasattr(prefs, 'draw'):
                        if align_box_draw:
                            col = column.box().column()
                        else:
                            col = box.column()

                        col_head = col.column()
                        col_body = col.column()
                        prefs.layout = col_body
                        has_error = False
                        try:
                            prefs.draw(context)
                        except:
                            traceback.print_exc()
                            has_error = True
                        introspect = eval(col_body.introspect())
                        if introspect[0] or has_error:
                            if not align_box_draw:
                                sub = col_head.row()
                                sub.active = False  # 色を薄くする為
                                sub.label('―' * 40)
                            col_head.label('Preferences:')
                        if has_error:
                            col_body.label(text='Error (see console)',
                                           icon='ERROR')
                        del prefs.layout

        if '.' not in bl_idname:
            row = layout.row()
            # row.alignment = 'RIGHT'
            # sub = row.box().row()
            sub = row.row()
            sub.alignment = 'RIGHT'
            sub.prop(self, 'align_box_draw_')
            sub.prop(self, 'use_indent_draw_')


classes = [
    AddonGroupPreferencesMiscellaneous,
    AddonGroupPreferences,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes[::-1]:
        bpy.utils.unregister_class(cls)
