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
_bpy = bpy  # addon_utils.py用


class AddonPreferences:
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
            prefs = getattr(prefs, attr)
        return prefs

    @classmethod
    def register(cls):
        if '.' in cls.bl_idname:
            # 親オブジェクトへの登録。
            # ctools以外での使用を想定していない
            U = bpy.context.user_preferences
            attrs = cls.bl_idname.split('.')
            base_prop = U.addons[attrs[0]].preferences
            for attr in attrs[1:-1]:
                base_prop = getattr(base_prop, attr)
            prop = bpy.props.PointerProperty(type=cls)

            if isinstance(base_prop, bpy.types.PropertyGroup):  # 汎用
                setattr(base_prop.__class__, attrs[-1], prop)
            else:  # ctools用
                setattr(base_prop, attrs[-1], prop)

        c = super()
        if hasattr(c, 'register'):
            c.register()

    @classmethod
    def unregister(cls):
        if '.' in cls.bl_idname:
            # 親オブジェクトからの登録解除。
            # ctools以外での使用を想定していない
            U = bpy.context.user_preferences
            attrs = cls.bl_idname.split('.')
            base_prop = U.addons[attrs[0]].preferences
            for attr in attrs[1:-1]:
                base_prop = getattr(base_prop, attr)
            if isinstance(base_prop, bpy.types.PropertyGroup):  # 汎用
                delattr(base_prop.__class__, attrs[-1])
            else:  # ctools用
                delattr(base_prop, attrs[-1])

        c = super()
        if hasattr(c, 'unregister'):
            c.unregister()


class SpaceProperty:
    """
    bpy.types.Spaceに仮想的なプロパティを追加

    # インスタンス生成
    space_prop = SpaceProperty(
        [[bpy.types.SpaceView3D, 'lock_cursor_location',
          bpy.props.BoolProperty()]])

    # 描画時
    def draw(self, context):
        layout = self.layout
        view = context.space_data
        prop = space_prop.get_prop(view, 'lock_cursor_location')
        layout.prop(prop, 'lock_cursor_location')

    # register / unregister
    def register():
        space_prop.register()

    def unregister():
        space_prop.unregister()
    """

    space_types = {
        'EMPTY': bpy.types.Space,
        'NONE': bpy.types.Space,
        'CLIP_EDITOR': bpy.types.SpaceClipEditor,
        'CONSOLE': bpy.types.SpaceConsole,
        'DOPESHEET_EDITOR': bpy.types.SpaceDopeSheetEditor,
        'FILE_BROWSER': bpy.types.SpaceFileBrowser,
        'GRAPH_EDITOR': bpy.types.SpaceGraphEditor,
        'IMAGE_EDITOR': bpy.types.SpaceImageEditor,
        'INFO': bpy.types.SpaceInfo,
        'LOGIC_EDITOR': bpy.types.SpaceLogicEditor,
        'NLA_EDITOR': bpy.types.SpaceNLA,
        'NODE_EDITOR': bpy.types.SpaceNodeEditor,
        'OUTLINER': bpy.types.SpaceOutliner,
        'PROPERTIES': bpy.types.SpaceProperties,
        'SEQUENCE_EDITOR': bpy.types.SpaceSequenceEditor,
        'TEXT_EDITOR': bpy.types.SpaceTextEditor,
        'TIMELINE': bpy.types.SpaceTimeline,
        'USER_PREFERENCES': bpy.types.SpaceUserPreferences,
        'VIEW_3D': bpy.types.SpaceView3D,
    }
    # space_types_r = {v: k for k, v in space_types.items()}

    def __init__(self, *props):
        """
        :param props: [[space_type, attr, prop], ...]
            [[文字列かbpy.types.Space, 文字列,
              bpy.props.***()かPropertyGroup], ...]
            bpy.types.PropertyGroupを使う場合はあらかじめregister_class()で
            登録しておく
        :type props: list[list]
        """
        self.props = [list(elem) for elem in props]
        for elem in self.props:
            space_type = elem[0]
            if isinstance(space_type, str):
                elem[0] = self.space_types[space_type]
        self.registered = []
        self.save_pre = self.save_post = self.load_post = None

    def gen_save_pre(self):
        @bpy.app.handlers.persistent
        def save_pre(dummy):
            wm = bpy.context.window_manager
            for (space_type, attr, prop), (cls, wm_prop_name) in zip(
                    self.props, self.registered):
                if wm_prop_name not in wm:
                    continue
                d = {p['name']: p for p in wm[wm_prop_name]}  # not p.name
                for screen in bpy.data.screens:
                    ls = []
                    for area in screen.areas:
                        for space in area.spaces:
                            if isinstance(space, space_type):
                                key = str(space.as_pointer())
                                if key in d:
                                    ls.append(d[key])
                                else:
                                    ls.append({})
                    screen[wm_prop_name] = ls
        self.save_pre = save_pre
        return save_pre

    def gen_save_post(self):
        @bpy.app.handlers.persistent
        def save_post(dummy):
            # 掃除
            for cls, wm_prop_name in self.registered:
                for screen in bpy.data.screens:
                    if wm_prop_name in screen:
                        del screen[wm_prop_name]
        self.save_post = save_post
        return save_post

    def gen_load_post(self):
        @bpy.app.handlers.persistent
        def load_post(dummy):
            from collections import OrderedDict
            for (space_type, attr, prop), (cls, wm_prop_name) in zip(
                    self.props, self.registered):
                d = OrderedDict()
                for screen in bpy.data.screens:
                    if wm_prop_name not in screen:
                        continue

                    spaces = []
                    for area in screen.areas:
                        for space in area.spaces:
                            if isinstance(space, space_type):
                                spaces.append(space)

                    for space, p in zip(spaces, screen[wm_prop_name]):
                        key = p['name'] = str(space.as_pointer())
                        d[key] = p
                if d:
                    bpy.context.window_manager[wm_prop_name] = list(d.values())

            # 掃除
            for cls, wm_prop_name in self.registered:
                for screen in bpy.data.screens:
                    if wm_prop_name in screen:
                        del screen[wm_prop_name]

        self.load_post = load_post
        return load_post

    def get_all(self, space_type=None, attr=''):
        """
        :param space_type: プロパティが一つだけの場合のみ省略可
        :type space_type: bpy.types.Space
        :param attr: プロパティが一つだけの場合のみ省略可
        :type attr: str
        :return:
        :rtype:
        """
        if space_type and isinstance(space_type, str):
            space_type = self.space_types.get(space_type)
        context = bpy.context
        for (st, attri, prop), (cls, wm_prop_name) in zip(
                self.props, self.registered):
            if (st == space_type or issubclass(space_type, st) or
                    not space_type and len(self.props) == 1):
                if attri == attr or not attr and len(self.props) == 1:
                    seq = getattr(context.window_manager, wm_prop_name)
                    return seq

    def get(self, space, attr=''):
        """
        :type space: bpy.types.Space
        :param attr: プロパティが一つだけの場合のみ省略可
        :type attr: str
        :return:
        :rtype:
        """
        seq = self.get_all(type(space), attr)
        if seq is not None:
            key = str(space.as_pointer())
            if key not in seq:
                item = seq.add()
                item.name = key
            return seq[key]

    def _property_name(self, space_type, attr):
        return space_type.__name__.lower() + '_' + attr

    def register(self):
        import inspect
        for space_type, attr, prop in self.props:
            if inspect.isclass(prop) and \
                    issubclass(prop, bpy.types.PropertyGroup):
                cls = prop
            else:
                name = 'WM_PG_' + space_type.__name__ + '_' + attr
                cls = type(name, (bpy.types.PropertyGroup,), {attr: prop})
                bpy.utils.register_class(cls)

            collection_prop = bpy.props.CollectionProperty(type=cls)
            wm_prop_name = self._property_name(space_type, attr)
            setattr(bpy.types.WindowManager, wm_prop_name, collection_prop)

            self.registered.append((cls, wm_prop_name))

            def gen():
                def get(self):
                    seq = getattr(bpy.context.window_manager, wm_prop_name)
                    key = str(self.as_pointer())
                    if key not in seq:
                        item = seq.add()
                        item.name = key
                    if prop == cls:
                        return seq[key]
                    else:
                        return getattr(seq[key], attr)

                def set(self, value):
                    seq = getattr(bpy.context.window_manager, wm_prop_name)
                    key = str(self.as_pointer())
                    if key not in seq:
                        item = seq.add()
                        item.name = key
                    if prop != cls:  # PropertyGroupは書き込み不可
                        return setattr(seq[key], attr, value)

                return property(get, set)

            setattr(space_type, attr, gen())

        bpy.app.handlers.save_pre.append(self.gen_save_pre())
        bpy.app.handlers.save_post.append(self.gen_save_post())
        bpy.app.handlers.load_post.append(self.gen_load_post())

    def unregister(self):
        bpy.app.handlers.save_pre.remove(self.save_pre)
        bpy.app.handlers.save_post.remove(self.save_post)
        bpy.app.handlers.load_post.remove(self.load_post)

        for (space_type, attr, prop), (cls, wm_prop_name) in zip(
                self.props, self.registered):
            delattr(bpy.types.WindowManager, wm_prop_name)
            if wm_prop_name in bpy.context.window_manager:
                del bpy.context.window_manager[wm_prop_name]
            delattr(space_type, attr)

            if prop != cls:
                # 元々がbpy.types.PropertyGroupなら飛ばす
                bpy.utils.unregister_class(cls)

            for screen in bpy.data.screens:
                if wm_prop_name in screen:
                    del screen[wm_prop_name]

        self.registered.clear()


def operator_call(op, *args, _scene_update=True, **kw):
    """vawmより
    operator_call(bpy.ops.view3d.draw_nearest_element,
                  'INVOKE_DEFAULT', type='ENABLE', _scene_update=False)
    """
    import bpy
    from _bpy import ops as ops_module

    BPyOpsSubModOp = op.__class__
    op_call = ops_module.call
    context = bpy.context

    # Get the operator from blender
    wm = context.window_manager

    # run to account for any rna values the user changes.
    if _scene_update:
        BPyOpsSubModOp._scene_update(context)

    if args:
        C_dict, C_exec, C_undo = BPyOpsSubModOp._parse_args(args)
        ret = op_call(op.idname_py(), C_dict, kw, C_exec, C_undo)
    else:
        ret = op_call(op.idname_py(), None, kw)

    if 'FINISHED' in ret and context.window_manager == wm:
        if _scene_update:
            BPyOpsSubModOp._scene_update(context)

    return ret


def is_main_loop_scene_update(context, scene):
    """bpy.app.handlers.scene_update_pre(post) へ追加した関数の中で呼ぶ。
    それがメインループから呼ばれたものか否かを返す。完全な判定は期待できない。
    :type context: bpy.types.Context
    :param scene: bpy.app.handlers.scene_update_pre(post) の引数。
    :type scene: bpy.types.Scene
    :rtype: bool
    """
    win = context.window
    scr = context.screen
    scn = context.scene
    if win and scr and scn:
        if scr == win.screen and scn == scr.scene == scene:
            if not context.region:  # wm_event_do_notifiers()参照
                return True
    return False


class AutoSaveManager:
    """
    modal operator の実行中は auto save が無効化されるので、このクラスを使って
    ファイルを保存する。

    例:

    class ModalOperator(bpy.types.Operator):
        def modal(self, context, event):
            auto_save_manager.save(context)

    auto_save_manager = utils.AutoSaveManager()

    def register():
        auto_save_manager.register()

    def unregister():
        auto_save_manager.unregister()

    """

    ignore_operators = [
        'VIEW3D_OT_region_ruler',
        'VIEW3D_OT_draw_nearest_element',
        'WM_OT_screencast_keys',
    ]

    ATTR = [bpy.types.WindowManager, 'auto_save_manager']

    # @classmethod
    # def get_callback(cls):
    #     handlers = bpy.app.handlers.scene_update_pre
    #     for func in handlers:
    #         if hasattr(func, '__func__'):
    #             f = func.__func__
    #             if hasattr(f, '__qualname__'):
    #                 if f.__qualname__ == cls.__qualname__ + '.callback':
    #                     return func

    # TODO: クラスメソッドにする
    def global_instance(self, create=True):
        """
        :rtype: AutoSaveManager
        """
        wm_type, attr = self.ATTR
        inst = getattr(wm_type, attr, None)
        if not inst and create:
            setattr(wm_type, attr, self)
            inst = self
        return inst

    def users_load(self):
        self_ = self.global_instance(create=False)
        return [obj for obj in self_.users if obj.registered_load]

    def users_scene_update(self):
        self_ = self.global_instance(create=False)
        return [obj for obj in self_.users if obj.registered_scene_update]

    def register(self, load=True, scene_update=False):
        if not self.registered:
            self.registered = True
            self_ = self.global_instance()
            self_.users.append(self)
            if load:
                if not self.registered_load:
                    self.registered_load = True
                    if len(self_.users_load()) == 1:
                        bpy.app.handlers.load_post.append(self_.load_callback)
            if scene_update:
                if not self.registered_scene_update:
                    self.registered_scene_update = True
                    if len(self_.users_scene_update()) == 1:
                        bpy.app.handlers.scene_update_pre.append(
                            self_.scene_update_callback)

    def unregister(self):
        if self.registered:
            self.registered = False
            self_ = self.global_instance()
            self_.users.remove(self)
            # 不要なコールバックの削除
            if self.registered_load:
                self.registered_load = False
                if not self_.users_load():
                    bpy.app.handlers.load_post.remove(self_.load_callback)
            if self.registered_scene_update:
                self.registered_scene_update = False
                if not self_.users_scene_update():
                    bpy.app.handlers.scene_update_pre.remove(
                        self_.scene_update_callback)

            # 入れ替え
            wm_type, attr = self_.ATTR
            if self_.users:
                other = self_.users[0]
                other.path = self_.path
                other.save_time = self_.save_time
                other.failed_count = self_.failed_count
                other.users[:] = self_.users
                if self_.users_load():
                    bpy.app.handlers.load_post.remove(self_.load_callback)
                    bpy.app.handlers.load_post.append(other.load_callback)
                if self_.users_scene_update():
                    bpy.app.handlers.scene_update_pre.remove(
                        self_.scene_update_callback)
                    bpy.app.handlers.scene_update_pre.append(
                        other.scene_update_callback)
                setattr(wm_type, attr, other)
            else:
                delattr(wm_type, attr)

    @property
    def load_callback(self):
        # persistentのデコレート対象は関数限定(メソッド不可)で、一番外側で
        # デコレートしていないと無意味って事でわざわざこんな事してる。
        if not self._load_callback:
            @bpy.app.handlers.persistent
            def load_callback(scene):
                import time
                self_ = self.global_instance()
                self_.save_time = time.time()
                self_.failed_count = 0
            self._load_callback = load_callback
        return self._load_callback

    @property
    def scene_update_callback(self):
        if not self._scene_update_callback:
            @bpy.app.handlers.persistent
            def scene_update_callback(scene):
                if is_main_loop_scene_update(bpy.context, scene):
                    self_ = self.global_instance()
                    self_.save(bpy.context)
            self._scene_update_callback = scene_update_callback
        return self._scene_update_callback

    def __init__(self):
        import logging
        import time

        self.logger = logger = logging.getLogger(__name__)
        logger.setLevel(logging.WARNING)
        handler = logging.StreamHandler()
        handler.setLevel(logging.NOTSET)
        formatter = logging.Formatter(
            '%(asctime)s [%(levelname)s] '
            '[%(name)s.%(funcName)s():%(lineno)d]: '
            '%(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)

        self.users = []

        self.path = ''
        self.save_time = time.time()
        self.failed_count = 0

        self.registered = False
        self.registered_load = False
        self.registered_scene_update = False

        self._load_callback = None
        self._scene_update_callback = None

    def save(self, context):
        """
        :type context: bpy.context
        :rtype: bool
        """
        import os
        import platform
        import time
        import traceback

        try:
            from . import structures
        except:
            traceback.print_exc()
            structures = None

        file_prefs = context.user_preferences.filepaths
        if not file_prefs.use_auto_save_temporary_files:
            return None

        self_ = self.global_instance()

        cur_time = time.time()
        save_interval = file_prefs.auto_save_time * 60
        ofs_time = 10.0 * self_.failed_count
        # 指定時間に達しているか確認
        if cur_time - self_.save_time < save_interval + ofs_time:
            return None

        if structures:
            system_auto_save = True
            for win in context.window_manager.windows:
                handlers = structures.wmWindow.modal_handlers(
                    win)
                for handler, idname, sa, ar, rt in handlers:
                    if handler.op:
                        system_auto_save = False
                        if idname not in self_.ignore_operators:
                            self_.logger.debug(
                                "Modal operator <{}> is running. "
                                "Skip auto save".format(idname))
                            return None
            if system_auto_save:
                return None

        # 保存先となるパスを生成。wm_autosave_location()参照
        if bpy.data.is_saved:
            file_name = os.path.basename(bpy.data.filepath)
            save_base_name = os.path.splitext(file_name)[0] + '.blend'
        else:
            if platform.system() not in ('Linux', 'Windows'):
                # os.gitpid()が使用出来ず、ファイル名が再現出来無い為
                return None
            pid = os.getpid()
            save_base_name = str(pid) + '.blend'
        save_dir = os.path.normpath(
            os.path.join(bpy.app.tempdir, os.path.pardir))
        if platform.system() == 'Windows' and not os.path.exists(save_dir):
            save_dir = bpy.utils.user_resource('AUTOSAVE')
        save_path = self_.path = os.path.join(save_dir, save_base_name)

        # 既にファイルが存在して更新時間がself.save_timeより進んでいたら
        # その時間と同期する
        if os.path.exists(save_path):
            st = os.stat(save_path)
            if self_.save_time < st.st_mtime:
                self_.save_time = st.st_mtime
                self_.logger.debug("Auto saved file '{}' is updated".format(
                    save_path))
            if cur_time - self_.save_time < save_interval + ofs_time:
                return None

        self_.logger.debug("Try auto save '{}' ...".format(save_path))

        # ディレクトリ生成
        if not os.path.exists(save_dir):
            try:
                os.makedirs(save_dir)
            except:
                self_.logger.error("Unable to save '{}'".format(save_dir),
                                   exc_info=True)
                self_.failed_count += 1
                return False

        # cyclesレンダリング直後の場合、サムネイル作成でよく落ちるので切る。
        use_save_preview = file_prefs.use_save_preview_images
        file_prefs.use_save_preview_images = False
        # Save
        try:
            bpy.ops.wm.save_as_mainfile(
                False, filepath=save_path, compress=False, relative_remap=True,
                copy=True, use_mesh_compat=False)
        except:
            self_.logger.error("Unable to save '{}'".format(save_dir),
                               exc_info=True)
            self_.failed_count += 1
            saved = False
        else:
            self_.logger.info("Auto Save '{}'".format(save_path))
            # 設定し直す事で内部のタイマーがリセットされる
            self_.save_time = os.stat(save_path).st_mtime
            self_.failed_count = 0
            file_prefs.auto_save_time = file_prefs.auto_save_time
            saved = True
        file_prefs.use_save_preview_images = use_save_preview
        return saved


"""
BKE_context.h:
enum {
    CTX_MODE_EDIT_MESH = 0,
    CTX_MODE_EDIT_CURVE,
    CTX_MODE_EDIT_SURFACE,
    CTX_MODE_EDIT_TEXT,
    CTX_MODE_EDIT_ARMATURE,
    CTX_MODE_EDIT_METABALL,
    CTX_MODE_EDIT_LATTICE,
    CTX_MODE_POSE,
    CTX_MODE_SCULPT,
    CTX_MODE_PAINT_WEIGHT,
    CTX_MODE_PAINT_VERTEX,
    CTX_MODE_PAINT_TEXTURE,
    CTX_MODE_PARTICLE,
    CTX_MODE_OBJECT
};

context.c:
static const char *data_mode_strings[] = {
    "mesh_edit",
    "curve_edit",
    "surface_edit",
    "text_edit",
    "armature_edit",
    "mball_edit",
    "lattice_edit",
    "posemode",
    "sculpt_mode",
    "weightpaint",
    "vertexpaint",
    "imagepaint",
    "particlemode",
    "objectmode",
    NULL
};


"""