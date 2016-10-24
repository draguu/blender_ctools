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
    'name': 'File Browser Confirm',
    'author': 'chromoly',
    'version': (0, 1, 1),
    'blender': (2, 78, 0),
    'location': 'File Browser',
    'description': '',
    'warning': '',
    'wiki_url': '',
    'tracker_url': '',
    'category': 'User Interface',
}


import ctypes as ct
import importlib
import os
import re

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


translation_dict = {
    'ja_JP': {
        ('Operator', 'Overwrite'): '上書き保存',
        ('*', 'Overwrite existing file'): '上書き保存',
        ('*', 'separator: ","\ne.g. "image.save_as, wm.save_as_mainfile"'):
            'オペレーターを "," で区切って記述します\n'
            '例: "image.save_as, wm.save_as_mainfile"',
    }
}


class SaveConfirmPreferences(
        addongroup.AddonGroupPreferences,
        registerinfo.AddonRegisterInfo,
        bpy.types.PropertyGroup if '.' in __name__ else
        bpy.types.AddonPreferences):
    bl_idname = __name__

    save_operators = bpy.props.StringProperty(
        name='Save',
        description='separator: ","\n'
                    'e.g. "image.save_as, wm.save_as_mainfile"',
        default='image.save_as',
    )

    def draw(self, context):
        layout = self.layout
        column = layout.column()
        sp = column.split(0.15)
        col = sp.column()
        text = bpy.app.translations.pgettext_iface('Operator') + ':'
        col.label(text)
        col = sp.column()
        col.prop(self, 'save_operators', text='')

        self.layout.separator()
        super().draw(context)


OPERATOR_RUNNING_MODAL = (1 << 0)
OPERATOR_CANCELLED = (1 << 1)
OPERATOR_FINISHED = (1 << 2)
# add this flag if the event should pass through
OPERATOR_PASS_THROUGH = (1 << 3)
# in case operator got executed outside WM code... like via fileselect
OPERATOR_HANDLED = (1 << 4)
# used for operators that act indirectly (eg. popup menu)
# note: this isn't great design (using operators to trigger UI) avoid where possible.
OPERATOR_INTERFACE = (1 << 5)


class FILE_OT_execute(bpy.types.Operator):
    bl_idname = 'file.execute'
    bl_label = 'Execute File Window'
    bl_description = 'Execute selected file'

    operator_type = None

    need_active = bpy.props.BoolProperty(
        name='Need Active',
        description="Only execute if there's an active selected file in the "
                    "file list",
        default=False,
        options={'SKIP_SAVE'}
    )

    @classmethod
    def poll(cls, context):
        if cls.operator_type is None:
            return False
        func_type = ct.CFUNCTYPE(ct.c_bool, ct.c_void_p)
        func = ct.cast(cls.operator_type.poll, func_type)
        return func(context.as_pointer())

    def call_internal(self, context):
        ot = FILE_OT_execute.operator_type
        func_type = ct.CFUNCTYPE(ct.c_int, ct.c_void_p, ct.c_void_p)
        func = ct.cast(ot.exec, func_type)
        result = func(context.as_pointer(), self.as_pointer())

        r = set()
        return_flags = {
            OPERATOR_RUNNING_MODAL: 'RUNNING_MODAL',
            OPERATOR_CANCELLED: 'CANCELLED',
            OPERATOR_FINISHED: 'FINISHED',
            OPERATOR_PASS_THROUGH: 'PASS_THROUGH',
            # OPERATOR_HANDLED: '',  # python api には無い
            OPERATOR_INTERFACE: 'INTERFACE',
        }
        for k, v in return_flags.items():
            if result & k:
                r.add(v)
        return r

    def to_bl_idnames(self, text):
        bl_idnames = []
        text = re.sub('\s*,\s*', ',', text).strip(' ')
        for name in text.split(','):
            if '.' in name:
                m, f = name.split('.')
                bl_idnames.append(m.upper() + '_OT_' + f)
            else:
                bl_idnames.append(name)
        return bl_idnames

    # NODE: FileBrowserでボタンを押した場合はexecuteが、
    #       Enterキーを押した場合はinvokeが呼ばれる。

    def execute(self, context):
        prefs = SaveConfirmPreferences.get_instance()
        space_file = context.space_data
        op = space_file.active_operator  # 値はspace_file.operatorと同じ

        # save用
        bl_idnames = self.to_bl_idnames(prefs.save_operators)
        if op and op.bl_idname in bl_idnames:
            if 0:
                # 起動直後にディレクトに変更を加えず保存する場合は
                # op.filepathがファイル名のみでディレクトリ情報を含んでいない
                path = op.filepath
                if path.startswith('//') and bpy.data.filepath:
                    blend_dir = os.path.dirname(bpy.data.filepath)
                    path = os.path.normpath(os.path.join(blend_dir, path[2:]))
            else:
                path = os.path.join(space_file.params.directory,
                                    space_file.params.filename)
            if os.path.exists(path):
                return bpy.ops.file.execute_overwrite_confirm(
                    'INVOKE_DEFAULT', need_active=self.need_active)

        return self.call_internal(context)


class FILE_OT_execute_overwrite_confirm(bpy.types.Operator):
    bl_idname = 'file.execute_overwrite_confirm'
    bl_label = 'Overwrite'
    bl_description = 'Overwrite existing file'
    bl_options = {'REGISTER', 'INTERNAL'}

    need_active = bpy.props.BoolProperty(
        name='Need Active',
        description="Only execute if there's an active selected file in the "
                    "file list",
        default=False,
        options={'SKIP_SAVE'}
    )

    def execute(self, context):
        return FILE_OT_execute.call_internal(self, context)

    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_confirm(self, event)


classes = [
    SaveConfirmPreferences,
    FILE_OT_execute,
    FILE_OT_execute_overwrite_confirm,
]


@SaveConfirmPreferences.module_register
def register():
    # オリジナルのwmOperatorTypeを確保しておく
    pyop = bpy.ops.file.execute
    opinst = pyop.get_instance()
    pyrna = ct.cast(id(opinst), ct.POINTER(structures.BPy_StructRNA)).contents
    op = ct.cast(pyrna.ptr.data,
                 ct.POINTER(structures.wmOperator)).contents
    FILE_OT_execute.operator_type = op.type.contents

    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.app.translations.register(__name__, translation_dict)


@SaveConfirmPreferences.module_unregister
def unregister():
    for cls in classes[::-1]:
        bpy.utils.unregister_class(cls)
    bpy.app.translations.unregister(__name__)


if __name__ == '__main__':
    register()
