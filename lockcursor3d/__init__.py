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
    'version': (0, 3, 3),
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


import ctypes as ct
import importlib

import bpy

try:
    importlib.reload(addongroup)
    importlib.reload(customproperty)
    importlib.reload(registerinfo)
    importlib.reload(structures)
except NameError:
    from . import addongroup
    from . import customproperty
    from . import registerinfo
    from . import structures


class LockCursorPreferences(
        addongroup.AddonGroupPreferences,
        registerinfo.AddonRegisterInfo,
        bpy.types.PropertyGroup if '.' in __name__ else
        bpy.types.AddonPreferences):
    bl_idname = __name__


class VIEW3D_OT_cursor3d(bpy.types.Operator):
    bl_idname = 'view3d.cursor3d'
    bl_label = 'Set 3D Cursor'
    bl_options = {'REGISTER'}

    operator_type = None

    @classmethod
    def poll(cls, context):
        func_type = ct.CFUNCTYPE(ct.c_bool, ct.c_void_p)
        func = ct.cast(cls.operator_type.poll, func_type)
        r = func(context.as_pointer())
        return r and not context.space_data.lock_cursor_location

    def invoke(self, context, event):
        ot = self.__class__.operator_type
        func_type = ct.CFUNCTYPE(ct.c_int, ct.c_void_p, ct.c_void_p,
                                 ct.c_void_p)
        func = ct.cast(ot.invoke, func_type)
        func(context.as_pointer(), None, event.as_pointer())
        return {'FINISHED'}


CustomProperty = customproperty.CustomProperty.new_class()


draw_func_bak = None


def panel_draw_set():
    global draw_func_bak

    def draw(self, context):
        layout = self.layout
        view = context.space_data

        custom_prop = CustomProperty.active()
        attrs = custom_prop.ensure(view, 'lock_cursor_location')
        attr = attrs['lock_cursor_location']
        layout.prop(custom_prop, attr)

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


classes = [
    LockCursorPreferences,
    VIEW3D_OT_cursor3d,
    CustomProperty,
]


@LockCursorPreferences.module_register
def register():
    pyop = bpy.ops.view3d.cursor3d
    opinst = pyop.get_instance()
    pyrna = ct.cast(id(opinst), ct.POINTER(structures.BPy_StructRNA)).contents
    op = ct.cast(pyrna.ptr.data,
                 ct.POINTER(structures.wmOperator)).contents
    VIEW3D_OT_cursor3d.operator_type = op.type.contents

    for cls in classes:
        bpy.utils.register_class(cls)

    CustomProperty.utils.register_space_property(
        bpy.types.SpaceView3D, 'lock_cursor_location',
        bpy.props.BoolProperty(
            name='Lock Cursor Location',
            description='3D Cursor location is locked to prevent it from '
                        'being accidentally moved')
    )

    panel_draw_set()


@LockCursorPreferences.module_unregister
def unregister():
    panel_draw_restore()

    CustomProperty.utils.unregister_space_property(
        bpy.types.SpaceView3D, 'lock_cursor_location',
    )

    for cls in classes[::-1]:
        bpy.utils.unregister_class(cls)


if __name__ == '__main__':
    register()
