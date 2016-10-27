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
    'name': 'Region Panel Categories',
    'author': 'chromoly',
    'version': (0, 1, 1),
    'blender': (2, 78, 0),
    # 'location': 'Screen',
    'description': "Add 'bpy.types.Region.panel_categories' and "
                   "'bpy.types.Region.active_panel_category'",
    'warning': 'Linux only',
    'wiki_url': '',
    'tracker_url': '',
    'category': 'User Interface',
}


import ctypes as ct
import importlib
import platform as _platform

import bpy

try:
    importlib.reload(addongroup)
    importlib.reload(registerinfo)
    importlib.reload(st)
except NameError:
    from . import addongroup
    from . import registerinfo
    from . import structures as st


platform = _platform.platform().split('-')[0].lower()
"""'linux', 'windows', 'darwin'
:type: str"""


if platform == 'linux':
    bl_cdll = ct.CDLL('')
else:
    bl_cdll = None


class TabSwitcherPreferences(
        addongroup.AddonGroupPreferences,
        registerinfo.AddonRegisterInfo,
        bpy.types.PropertyGroup if '.' in __name__ else
        bpy.types.AddonPreferences):
    bl_idname = __name__

    use_c_functions = bpy.props.BoolProperty(
        name='Use C Functions', default=True)

    def draw(self, context):
        layout = self.layout
        col = layout.column()
        col.enabled = platform == 'linux'
        col.prop(self, 'use_c_functions')

        self.layout.separator()
        super().draw(context)


class PanelCategoryDyn(ct.Structure):
    """DNA_screen_types.h: 131"""

PanelCategoryDyn._fields_ = st.fields(
    PanelCategoryDyn, '*next', '*prev',
    ct.c_char, 'idname[64]',
    st.rcti, 'rect'
)


class PanelCategoryStack(ct.Structure):
    """DNA_screen_types.h: 138"""

PanelCategoryStack._fields_ = st.fields(
    PanelCategoryStack, '*next', '*prev',
    ct.c_char, 'idname[64]',
)


BKE_ST_MAXNAME = 64


class PanelType(ct.Structure):
    """DNA_screen_types.h: 173"""

PanelType._fields_ = st.fields(
    PanelType, '*next', '*prev',
    ct.c_char * BKE_ST_MAXNAME, 'idname',
    ct.c_char * BKE_ST_MAXNAME, 'label',
    ct.c_char * BKE_ST_MAXNAME, 'translation_context',
    ct.c_char * BKE_ST_MAXNAME, 'context',
    ct.c_char * BKE_ST_MAXNAME, 'category',
    # (以下略)
)


def UI_panel_category_find(ar, idname):
    """
    :type ar: ARegion
    :type idname: bytes
    :rtype: PanelCategoryDyn
    """
    prefs = TabSwitcherPreferences.get_instance()
    if prefs.use_c_functions and bl_cdll:
        func = bl_cdll.UI_panel_category_find
        func.argtypes = [ct.c_void_p, ct.c_char_p]
        func.restype = ct.c_void_p
        addr = func(ct.addressof(ar), idname)
    else:
        addr = ar.panels_category.find_string(
            idname, PanelCategoryDyn.idname.offset)
    if addr:
        return ct.cast(addr, ct.POINTER(PanelCategoryDyn)).contents
    else:
        return None


def UI_panel_category_active_find(ar, idname):
    """
    :type ar: ARegion
    :type idname: bytes
    :rtype: PanelCategoryStack
    """
    prefs = TabSwitcherPreferences.get_instance()
    if prefs.use_c_functions and bl_cdll:
        func = bl_cdll.UI_panel_category_active_find
        func.argtypes = [ct.c_void_p, ct.c_char_p]
        func.restype = ct.c_void_p
        addr = func(ct.addressof(ar), idname)
    else:
        addr = ar.panels_category_active.find_string(
            idname, PanelCategoryStack.idname.offset)
    if addr:
        return ct.cast(addr, ct.POINTER(PanelCategoryStack)).contents
    else:
        return None


def UI_panel_category_active_get(ar, set_fallback=False):
    """
    :type ar: ARegion
    :type set_fallback: bool
    :rtype: bytes
    """
    prefs = TabSwitcherPreferences.get_instance()
    if prefs.use_c_functions and bl_cdll:
        func = bl_cdll.UI_panel_category_active_get
        func.argtypes = [ct.c_void_p, ct.c_bool]
        func.restype = ct.c_char_p
        return func(ct.addressof(ar), set_fallback)

    pc_act_p = ct.cast(ar.panels_category_active.first,
                       ct.POINTER(PanelCategoryStack))
    while pc_act_p:
        pc_act = pc_act_p.contents
        if UI_panel_category_find(ar, pc_act.idname):
            return pc_act.idname
        pc_act_p = pc_act.next

    if set_fallback:
        pc_dyn_p = ct.cast(ar.panels_category.first, PanelCategoryDyn)
        if pc_dyn_p:
            pc_dyn = pc_dyn_p.contents
            UI_panel_category_active_set(ar, pc_dyn.idname)
            return pc_dyn.idname

    return None


def UI_panel_category_active_set(ar, idname):
    """
    :type ar: ARegion
    :type idname: bytes
    """
    prefs = TabSwitcherPreferences.get_instance()
    if prefs.use_c_functions and bl_cdll:
        func = bl_cdll.UI_panel_category_active_set
        func.argtypes = [ct.c_void_p, ct.c_char_p]
        func(ct.addressof(ar), idname)
        return

    lb = ar.panels_category_active
    pc_act = UI_panel_category_active_find(ar, idname)
    if pc_act:
        lb.remove(pc_act)
    else:
        # FIXME: MEM_callocNの再現が不十分の為何が起こるか分からない
        ptr = st.MEM_callocN(ct.sizeof(PanelCategoryStack))  # 適当に増やす
        pc_act = ct.cast(ptr, ct.POINTER(PanelCategoryStack)).contents
        pc_act.idname = idname
    lb.insert(0, pc_act)

    # pc_act_next_p = pc_act.next
    # while pc_act_next_p:
    #     pc_act = pc_act_next_p.contents
    #     pc_act_next_p = pc_act.next
    #     if not ar.type.contents.paneltypes.find_string(
    #             pc_act.idname, PanelType.category.offset):
    #         lb.remove(pc_act)
    #         # free(addressof(pc_act))


def region_panel_categories_get(self):
    categories = []
    ar = ct.cast(self.as_pointer(), ct.POINTER(st.ARegion)).contents
    lb = ar.panels_category
    if lb.first:
        pc_dyn_p = ct.cast(lb.first, ct.POINTER(PanelCategoryDyn))
        while pc_dyn_p:
            pc_dyn = pc_dyn_p.contents
            categories.append(pc_dyn.idname.decode())
            pc_dyn_p = pc_dyn.next
    return categories


def region_active_panel_category_get(self):
    ar = ct.cast(self.as_pointer(), ct.POINTER(st.ARegion)).contents
    idname = UI_panel_category_active_get(ar)
    if idname is not None:
        idname = idname.decode()
    return idname


def region_active_panel_category_set(self, idname):
    ar = ct.cast(self.as_pointer(), ct.POINTER(st.ARegion)).contents
    categories = self.panel_categories
    if not categories:
        raise ValueError('Categories do not exist: {}'.format(self))
    if idname not in categories:
        raise ValueError("'{}' not in {}: {}".format(idname, categories, self))

    UI_panel_category_active_set(ar, idname.encode(encoding='utf-8'))


classes = [
    TabSwitcherPreferences
]


@TabSwitcherPreferences.module_register
def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Region.panel_categories = property(region_panel_categories_get)
    bpy.types.Region.active_panel_category = property(
        region_active_panel_category_get, region_active_panel_category_set)


@TabSwitcherPreferences.module_unregister
def unregister():
    for cls in classes[::-1]:
        bpy.utils.unregister_class(cls)

    del bpy.types.Region.panel_categories
    del bpy.types.Region.active_panel_category


if __name__ == '__main__':
    register()
