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


bl_info = {
    'name': 'My Addon',
    'version': (0, 1),
    'description': 'Addon group test. Root Addon',
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
        # AddonGroupPreferencesのdrawメソッドで子のアドオンの設定を表示する。
        super().draw(context)

    @classmethod
    def register(cls):
        # registerやunregisterクラスメソッドを定義するなら
        # addongrouppreferencesのメソッドも呼んでおくこと。
        super().register()

    @classmethod
    def unregister(cls):
        super().unregister()

classes = [
    MyAddonPreferences,
]


def register():
    # AddonGroupPreferencesが依存するクラスがあるので、
    # それを先に登録する必要がある。
    MyAddonPreferences.register_pre()

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
