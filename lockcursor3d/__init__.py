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
    'name': 'Lock 3D Cursor',
    'author': 'chromoly',
    'version': (0, 3, 2),
    'blender': (2, 78, 0),
    'location': '3D View',
    'description': 'commit a791153: 3D Cursor: Add option to lock it in place '
                   'to prevent accidental modification',
    'warning': '',
    'wiki_url': 'https://github.com/chromoly/lock_cursor3d',
    'tracker_url': '',
    'category': '3D View'
}

"""
commit a791153ca5e6f87d50396e188a3664b579884161
3D Cursor: Add option to lock it in place to prevent accidental modification

これを再現したものになります

各SpaceView3DのフラグはScreenのIDPropertyに保存されます
"""


import importlib

import bpy

try:
    importlib.reload(addongroup)
    importlib.reload(registerinfo)
    importlib.reload(utils)
except NameError:
    from . import addongroup
    from . import registerinfo
    from . import utils


space_prop = utils.SpaceProperty(
    [bpy.types.SpaceView3D,
     'lock_cursor_location',
     bpy.props.BoolProperty(
         name='Lock Cursor Location',
         description='3D Cursor location is locked to prevent it from being '
                     'accidentally moved')
     ]
)


class LockCursorPreferences(
        addongroup.AddonGroupPreferences,
        registerinfo.AddonRegisterInfo,
        bpy.types.PropertyGroup if '.' in __name__ else
        bpy.types.AddonPreferences):
    bl_idname = __name__


class VIEW3D_OT_cursor3d_override(bpy.types.Operator):
    bl_idname = 'view3d.cursor3d_override'
    bl_label = 'Override 3D Cursor Operator'
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return bpy.ops.view3d.cursor3d.poll()

    def invoke(self, context, event):
        kc = bpy.context.window_manager.keyconfigs.active
        km = kc.keymaps.get('3D View')
        if km:
            for kmi in km.keymap_items:
                if kmi.idname == 'view3d.cursor3d':
                    kmi.idname = 'view3d.cursor3d_restrict'
                    disabled_keymap_items.append((kc.name, km.name, kmi.id))

        return {'PASS_THROUGH'}


class VIEW3D_OT_cursor3d_restrict(bpy.types.Operator):
    bl_idname = 'view3d.cursor3d_restrict'
    bl_label = 'Set 3D Cursor'
    bl_options = set()

    @classmethod
    def poll(cls, context):
        if bpy.ops.view3d.cursor3d.poll():
            if not context.space_data.lock_cursor_location:
                return True
        return False

    def invoke(self, context, event):
        return bpy.ops.view3d.cursor3d(context.copy(), 'INVOKE_DEFAULT')


draw_func_bak = None


def panel_draw_set():
    global draw_func_bak

    def draw(self, context):
        layout = self.layout
        view = context.space_data
        layout.prop(space_prop.get(view), 'lock_cursor_location')
        col = layout.column()
        col.active = not view.lock_cursor_location
        col.prop(view, 'cursor_location', text='Location')
        if hasattr(view, 'use_cursor_snap_grid'):
            col = layout.column()
            U = context.user_preferences
            col.active = not U.view.use_mouse_depth_cursor
            col.prop(view, "use_cursor_snap_grid", text="Cursor to Grid")

    draw_func_bak = None

    cls = bpy.types.VIEW3D_PT_view3d_cursor
    if hasattr(cls.draw, '_draw_funcs'):
        # bpy_types.py: _GenericUI._dyn_ui_initialize
        for i, func in enumerate(cls.draw._draw_funcs):
            if func.__module__ == cls.__module__:
                cls.draw._draw_funcs[i] = draw
                draw_func_bak = func
                break
    else:
        draw_func_bak = cls.draw
        cls.draw = draw


def panel_draw_restore():
    cls = bpy.types.VIEW3D_PT_view3d_cursor
    if hasattr(cls.draw, '_draw_funcs'):
        if draw_func_bak:
            for i, func in enumerate(cls.draw._draw_funcs):
                if func.__module__ == __name__:
                    cls.draw._draw_funcs[i] = draw_func_bak
    else:
        cls.draw = draw_func_bak


disabled_keymap_items = []


classes = [
    LockCursorPreferences,
    VIEW3D_OT_cursor3d_override,
    VIEW3D_OT_cursor3d_restrict,
]


@LockCursorPreferences.module_register
def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    """
    NOTE: 特定Areaを最大化すると一時的なScreenが生成されるので
    lock_cursor_location属性はScreenでは不適。WindowManagerを使う。
    """
    space_prop.register()

    panel_draw_set()

    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    if kc:
        km = LockCursorPreferences.get_keymap('3D View')
        kmi = km.keymap_items.new(
            'view3d.cursor3d_override', 'ACTIONMOUSE', 'PRESS',
            head=True
        )


@LockCursorPreferences.module_unregister
def unregister():
    panel_draw_restore()

    space_prop.unregister()

    wm = bpy.context.window_manager
    for kc_name, km_name, kmi_id in disabled_keymap_items:
        kc = wm.keyconfigs.get(kc_name)
        if not kc:
            continue
        km = kc.keymaps.get(km_name)
        if not km:
            continue
        for kmi in km.keymap_items:
            if kmi.id == kmi_id:
                kmi.idname = 'view3d.cursor3d'
                break
    disabled_keymap_items.clear()

    for cls in classes[::-1]:
        bpy.utils.unregister_class(cls)


if __name__ == '__main__':
    register()
