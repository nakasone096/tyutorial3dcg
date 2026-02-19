bl_info = {
    "name": "3DCG Tutorial Simulator",
    "blender": (4, 2, 0),
    "version": (0, 4, 2),
    "author": "Daichi",
    "description": "Interactive 3D learning simulation for Blender",
    "category": "Education",
    "support": "COMMUNITY",
}

import bpy
import bmesh
import math
import time
from bpy.types import Operator, Panel, PropertyGroup
from bpy.props import IntProperty, BoolProperty, FloatVectorProperty, FloatProperty, CollectionProperty, StringProperty

# =====================================================
# VERTEX POSITION STORAGE
# =====================================================

class VertexPos(PropertyGroup):
    """Store vertex position for comparison"""
    co: FloatVectorProperty(size=3)

# =====================================================
# STAGE VALIDATION & UTILITIES
# =====================================================

class StageManager:
    
    @staticmethod
    def open_shader_editor_at_bottom():
        """Open Shader Editor at bottom and focus it (STABLE VERSION)"""
        try:
            context = bpy.context
            
            # Check if already open
            for area in context.screen.areas:
                if area.type == 'NODE_EDITOR':
                    print("✓ Shader Editor は既に表示されています")
                    return True
            
            # Find VIEW_3D
            view_area = None
            for area in context.screen.areas:
                if area.type == 'VIEW_3D':
                    view_area = area
                    break
            
            if not view_area:
                print("❌ VIEW_3D not found")
                return False
            
            # Save area list before split
            old_areas = set(context.screen.areas)
            
            # Split area
            override = {
                "window": context.window,
                "screen": context.screen,
                "area": view_area,
                "region": view_area.regions[-1],
            }
            
            bpy.ops.screen.area_split(
                override,
                direction='HORIZONTAL',
                factor=0.7
            )
            
            # Get new area by comparing with old list
            new_area = None
            for area in context.screen.areas:
                if area not in old_areas:
                    new_area = area
                    break
            
            if not new_area:
                print("❌ New area not found")
                return False
            
            # Convert to Shader Editor
            new_area.type = 'NODE_EDITOR'
            new_area.spaces.active.tree_type = 'ShaderNodeTree'
            
            # Focus on new area
            for region in new_area.regions:
                if region.type == 'WINDOW':
                    override = {
                        'window': context.window,
                        'screen': context.screen,
                        'area': new_area,
                        'region': region
                    }
                    bpy.ops.screen.screen_full_area(override)
                    bpy.ops.screen.back_to_previous(override)
                    break
            
            print("✓ Shader Editor を下部に表示し、フォーカスしました")
            return True
        
        except Exception as e:
            print(f"Error opening shader editor: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    @staticmethod
    def find_cube():
        """Find the cube in the scene"""
        try:
            for obj in bpy.data.objects:
                if obj.type == 'MESH' and "Cube" in obj.name:
                    return obj
        except Exception as e:
            print(f"Error finding cube: {e}")
        return None
    
    @staticmethod
    def find_sphere():
        """Find UV Sphere for sculpting"""
        try:
            for obj in bpy.data.objects:
                if obj.type == 'MESH' and "Sphere" in obj.name:
                    return obj
        except Exception as e:
            print(f"Error finding sphere: {e}")
        return None
    
    @staticmethod
    def get_bm(obj):
        """Get bmesh from object in edit mode"""
        try:
            if not obj or obj.type != 'MESH':
                return None
            if bpy.context.mode != 'EDIT_MESH':
                return None
            return bmesh.from_edit_mesh(obj.data)
        except Exception as e:
            print(f"Error getting bmesh: {e}")
            return None
    
    @staticmethod
    def get_mesh_element_count(obj):
        """Get mesh element counts"""
        try:
            if obj and obj.type == 'MESH' and obj.data:
                return len(obj.data.vertices), len(obj.data.edges), len(obj.data.polygons)
        except Exception as e:
            print(f"Error getting mesh element count: {e}")
        return 0, 0, 0
    
    @staticmethod
    def get_view3d_space(context):
        """Get the VIEW_3D space"""
        try:
            for area in context.screen.areas:
                if area.type == 'VIEW_3D':
                    for space in area.spaces:
                        if space.type == 'VIEW_3D':
                            return space
        except Exception as e:
            print(f"Error getting VIEW_3D space: {e}")
        return None
    
    @staticmethod
    def calculate_vertex_distance(v_co, init_co):
        """Calculate distance between two vertex positions"""
        try:
            dx = v_co[0] - init_co[0]
            dy = v_co[1] - init_co[1]
            dz = v_co[2] - init_co[2]
            return (dx*dx + dy*dy + dz*dz) ** 0.5
        except Exception as e:
            print(f"Error calculating vertex distance: {e}")
            return 0.0
    
    @staticmethod
    def is_in_sculpt_mode():
        """Check if currently in sculpt mode"""
        try:
            return bpy.context.mode == 'SCULPT'
        except:
            return False
    
    @staticmethod
    def is_undo_running():
        """Check if Undo is currently running"""
        try:
            return bpy.context.window_manager.undo_depth > 0
        except:
            return False
    
    @staticmethod
    def get_current_brush_name():
        """Get the name of the currently selected brush"""
        try:
            if bpy.context.tool_settings and bpy.context.tool_settings.sculpt:
                brush = bpy.context.tool_settings.sculpt.brush
                if brush:
                    return brush.name
        except Exception as e:
            print(f"Error getting brush name: {e}")
        return None
    
    @staticmethod
    def is_brush_type_selected(brush_type_name):
        """Check if a specific brush type is currently selected"""
        try:
            brush_name = StageManager.get_current_brush_name()
            if brush_name:
                return brush_type_name in brush_name
        except Exception as e:
            print(f"Error checking brush type: {e}")
        return False
    
    @staticmethod
    def get_vertex_deformation_amount(sphere, initial_positions):
        """Calculate total deformation amount from initial state"""
        try:
            if not sphere or not sphere.data or not sphere.data.vertices:
                return 0, 0.0
            
            moved = 0
            total_distance = 0.0
            
            current_vert_count = len(sphere.data.vertices)
            initial_vert_count = len(initial_positions)
            
            compare_count = min(current_vert_count, initial_vert_count)
            
            if compare_count == 0:
                return 0, 0.0
            
            for i in range(compare_count):
                try:
                    v = sphere.data.vertices[i]
                    if not v or v.co is None:
                        continue
                    
                    init_co = initial_positions[i].co
                    if not init_co:
                        continue
                    
                    dist = StageManager.calculate_vertex_distance(v.co, init_co)
                    if dist > 0.001:
                        moved += 1
                        total_distance += dist
                
                except (IndexError, AttributeError, RuntimeError):
                    continue
            
            return moved, total_distance
        
        except Exception as e:
            print(f"Error calculating deformation: {e}")
            return 0, 0.0
    
    @staticmethod
    def get_active_material(obj):
        """Get the active material from an object"""
        try:
            if not obj or not obj.data:
                return None
            if not obj.material_slots:
                return None
            if obj.active_material_index < 0:
                return None
            return obj.active_material
        except Exception as e:
            print(f"Error getting material: {e}")
            return None
    
    @staticmethod
    def get_principled_bsdf(material):
        """Get the Principled BSDF node from a material"""
        try:
            if not material or not material.use_nodes:
                return None
            
            for node in material.node_tree.nodes:
                if node.type == 'BSDF_PRINCIPLED':
                    return node
            return None
        except Exception as e:
            print(f"Error getting Principled BSDF: {e}")
            return None
    
    @staticmethod
    def check_image_texture_node_exists(obj):
        """Check if an Image Texture node with loaded image exists"""
        try:
            mat = StageManager.get_active_material(obj)
            if not mat or not mat.use_nodes:
                return False
            
            for node in mat.node_tree.nodes:
                if node.type == 'TEX_IMAGE':
                    if node.image is not None:
                        return True
            return False
        except Exception as e:
            print(f"Error checking image texture: {e}")
            return False
    
    @staticmethod
    def check_correct_node_link(obj):
        """Check if ImageTexture Color output is connected to Principled BSDF BaseColor input"""
        try:
            mat = StageManager.get_active_material(obj)
            if not mat or not mat.use_nodes:
                return False
            
            # Find Image Texture node
            image_texture_node = None
            bsdf_node = None
            
            for node in mat.node_tree.nodes:
                if node.type == 'TEX_IMAGE':
                    image_texture_node = node
                if node.type == 'BSDF_PRINCIPLED':
                    bsdf_node = node
            
            if not image_texture_node or not bsdf_node:
                return False
            
            # Check if there's a link from ImageTexture.Color to BSDF.BaseColor
            for link in mat.node_tree.links:
                # Check if link goes from ImageTexture output to BSDF input
                if link.from_node == image_texture_node and link.to_node == bsdf_node:
                    # Check if it's the Color output to BaseColor input
                    if link.from_socket.name == 'Color' and link.to_socket.name == 'Base Color':
                        return True
            
            return False
        except Exception as e:
            print(f"Error checking node link: {e}")
            return False
    
    @staticmethod
    def get_stage_info(chapter_num, stage_num):
        """Get information about a stage"""
        if chapter_num == 1:
            stages = {
                1: {"title": "第1章: 基本操作", "name": "ステージ1: キューブを選択", 
                    "description": "キューブを選択してください", "control": "", "manual": False},
                2: {"title": "第1章: 基本操作", "name": "ステージ2: キューブを移動", 
                    "description": "X軸方向に+2移動", "control": "", "manual": False},
                3: {"title": "第1章: 基本操作", "name": "ス���ージ3: キューブを回転", 
                    "description": "X軸周りに45度回転", "control": "", "manual": False},
                4: {"title": "第1章: 基本操作", "name": "ステージ4: スケール変更", 
                    "description": "サイズを変更", "control": "", "manual": False},
            }
        elif chapter_num == 2:
            stages = {
                1: {"title": "第2章: ビュー操作", "name": "ステージ1: ビューを移動", 
                    "description": "Shift + 中ボタンでパン", "control": "Shift + 中ボタンドラッグ", "manual": False},
                2: {"title": "第2章: ビュー操作", "name": "ステージ2: ズーム", 
                    "description": "中ボタンスクロール", "control": "中ボタンスクロール", "manual": False},
                3: {"title": "第2章: ビュー操作", "name": "ステージ3: ビュー回転", 
                    "description": "中ボタンドラッグ", "control": "中ボタンドラッグ", "manual": False},
                4: {"title": "第2章: ビュー操作", "name": "ステージ4: すべてマスター", 
                    "description": "すべての操作を実行", "control": "すべてのビュー操作", "manual": False},
            }
        elif chapter_num == 3:
            stages = {
                1: {"title": "第3章: モデリング基礎", "name": "ステージ1: エディットモード", 
                    "description": "Tab キーで切り替え", "control": "Tab キー", "manual": False},
                2: {"title": "第3章: モデリング基礎", "name": "ステージ2: 頂点選択", 
                    "description": "3個以上の頂点を選択", "control": "1 キー", "manual": False},
                3: {"title": "第3章: モデリング基礎", "name": "ステージ3: エッジ選択", 
                    "description": "エッジを選択", "control": "2 キー", "manual": False},
                4: {"title": "第3章: モデリング基礎", "name": "ステージ4: フェース選択", 
                    "description": "フェースを選択", "control": "3 キー", "manual": False},
                5: {"title": "第3章: モデリング基礎", "name": "ステージ5: エクストルード", 
                    "description": "E キーで押し出し", "control": "E キー", "manual": False},
                6: {"title": "第3章: モデリング基礎", "name": "ステージ6: ループカット", 
                    "description": "Ctrl+R でループカット", "control": "Ctrl+R", "manual": False},
            }
        elif chapter_num == 4:
            stages = {
                1: {"title": "第4章: スカルプティング体験", "name": "ステージ1: スカルプトモード", 
                    "description": "Sculpt Mode に入ってください", "control": "", "manual": False},
                2: {"title": "第4章: スカルプティング体験", "name": "ステージ2: Draw ブラシを使う", 
                    "description": "Draw ブラシで球の表面を変形", "control": "Draw ブラシでドラッグ", "manual": False,
                    "tip": "💡 ヒント: 自由に実験してみよう!"},
                3: {"title": "第4章: スカルプティング体験", "name": "ステージ3: Smooth ブラシに切り替え", 
                    "description": "Smooth ブラシを選択してください", "control": "Smooth ブラシを選択", "manual": False,
                    "tip": "💡 ヒント: 自由に実験してみよう!"},
                4: {"title": "第4章: スカルプティング体験", "name": "ステージ4: Grab ブラシに切り替え", 
                    "description": "Grab ブラシを選択してください", "control": "Grab ブラシを選択", "manual": False,
                    "tip": "💡 ヒント: 自由に実験してみよう!"},
            }
        elif chapter_num == 5:
            stages = {
                1: {"title": "第5章: マテリアルノード", "name": "🟢 ステージ1: マテリアル作成", 
                    "description": "「新規」ボタンを押す",
                    "details": "上部メニューの 「シェーディング」 を選択し,\n表示されたタブの 「新規」 ボタンを押してマテリアルを作成しよう!",
                    "control": "", "manual": False},
                2: {"title": "第5章: マテリアルノード", "name": "🟢 ステージ2: 色変更", 
                    "description": "Base Color を変更",
                    "details": "「プリンシプルBSDF」ノードの\nベースカラー を変更して,オブジェクトの色を変えてみよう!",
                    "control": "", "manual": False},
                3: {"title": "第5章: マテリアルノード", "name": "🟢 ステージ3: 画像テクスチャ追加", 
                    "description": "追加 → 画像テクスチャで画像読み込み",
                    "details": "メニューから\n\n追加 → テクスチャ → 画像テクスチャ\n\nを選択し,好きな画像を読み込んでみよう!",
                    "control": "", "manual": False},
                4: {"title": "第5章: マテリアルノード", "name": "🟢 ステージ4: ノード接続", 
                    "description": "ImageTexture → BaseColor に接続",
                    "details": "ImageTexture ノードの Color 出力を\nPrincipled BSDF のベースカラー入力に接続してみよう!",
                    "control": "", "manual": False},
                5: {"title": "第5章: マテリアルノード", "name": "🟢 ステージ5: 質感調整", 
                    "description": "Roughness または Metallic を変更",
                    "details": "Principled BSDF の\nラフネス または メタリック を変更して,\nリアルな素材の見た目を作ってみよう!",
                    "control": "", "manual": False},
            }
        else:
            return {}
        
        return stages.get(stage_num, {})
    
    @staticmethod
    def validate_stage(context):
        """Validate current stage and return (is_complete, message)"""
        try:
            props = context.scene.tutorial_props
            current_chapter = props.current_chapter
            current_stage = props.current_stage
            obj = context.active_object
            
            if current_chapter == 1:
                # ============ CHAPTER 1 ============
                
                if current_stage == 1:
                    if obj and obj.name == "Cube":
                        return True, "✓ キューブが選択されました"
                    return False, "❌ キューブを選択してください"
                
                elif current_stage == 2:
                    if obj and obj.name == "Cube":
                        movement = obj.location.x - props.initial_position[0]
                        if abs(movement - 2.0) < 0.1:
                            return True, "✓ +2移動しました"
                        return False, f"❌ 移動: {movement:.2f}"
                    return False, "❌ キューブなし"
                
                elif current_stage == 3:
                    if obj and obj.name == "Cube":
                        rot = math.degrees(obj.rotation_euler.x) - math.degrees(props.initial_rotation[0])
                        if abs(rot - 45.0) < 1.0:
                            return True, "✓ 45度回転しました"
                        return False, f"❌ 回転: {rot:.1f}°"
                    return False, "❌ キューブなし"
                
                elif current_stage == 4:
                    if obj and obj.name == "Cube":
                        scale_changed = (abs(obj.scale.x - props.initial_scale[0]) > 0.01)
                        if scale_changed:
                            return True, "✓ スケール変更完了"
                        return False, "❌ スケール値を変更してください"
                    return False, "❌ キューブなし"
            
            elif current_chapter == 2:
                # ============ CHAPTER 2 ============
                
                space = StageManager.get_view3d_space(context)
                if not space or not space.region_3d:
                    return False, "❌ 3Dビューなし"
                
                region_3d = space.region_3d
                
                if current_stage == 1:
                    loc_diff = sum((region_3d.view_location[i] - props.initial_view_location[i])**2 
                                  for i in range(3))**0.5
                    if loc_diff > 0.1:
                        return True, "✓ ビュー移動完了"
                    return False, "❌ ビューをパンしてください"
                
                elif current_stage == 2:
                    dist_diff = abs(region_3d.view_distance - props.initial_view_distance)
                    if dist_diff > 0.5:
                        return True, "✓ ズーム完了"
                    return False, "❌ ズームしてください"
                
                elif current_stage == 3:
                    loc_diff = sum((region_3d.view_location[i] - props.initial_view_location[i])**2 
                                  for i in range(3))**0.5
                    dist_diff = abs(region_3d.view_distance - props.initial_view_distance)
                    if loc_diff > 0.01 or dist_diff > 0.01:
                        return True, "✓ ビュー回転完了"
                    return False, "❌ ビューを回転させてください"
                
                elif current_stage == 4:
                    loc_diff = sum((region_3d.view_location[i] - props.initial_view_location[i])**2 
                                  for i in range(3))**0.5
                    dist_diff = abs(region_3d.view_distance - props.initial_view_distance)
                    if loc_diff > 0.1 and dist_diff > 0.5:
                        return True, "✓ すべてのビュー操作をマスターしました"
                    return False, "❌ パン + ズームを実行してください"
            
            elif current_chapter == 3:
                # ============ CHAPTER 3 ============
                
                if current_stage == 1:
                    if obj and bpy.context.mode == 'EDIT_MESH':
                        return True, "✓ エディットモード突入"
                    return False, "❌ エディットモードに入ってください"
                
                elif current_stage == 2:
                    bm = StageManager.get_bm(obj)
                    if bm:
                        sel_count = sum(1 for v in bm.verts if v.select)
                        if sel_count >= 3:
                            return True, f"✓ 頂点選択: {sel_count}個"
                        return False, f"❌ 頂点を選択してください ({sel_count}個)"
                    return False, "❌ エディットモード必須"
                
                elif current_stage == 3:
                    bm = StageManager.get_bm(obj)
                    if bm and any(e.select for e in bm.edges):
                        return True, "✓ エッジ選択完了"
                    return False, "❌ エッジを選択してください"
                
                elif current_stage == 4:
                    bm = StageManager.get_bm(obj)
                    if bm and any(f.select for f in bm.faces):
                        return True, "✓ フェース選択完了"
                    return False, "❌ フェースを選択してください"
                
                elif current_stage == 5:
                    bm = StageManager.get_bm(obj)
                    if bm and len(bm.faces) > props.initial_face_count:
                        return True, f"✓ 押し出し完了: {props.initial_face_count}→{len(bm.faces)}"
                    return False, "❌ 面を押し出してください"
                
                elif current_stage == 6:
                    bm = StageManager.get_bm(obj)
                    if bm and len(bm.verts) > props.initial_vertex_count:
                        return True, f"✓ ループカット完了: {props.initial_vertex_count}��{len(bm.verts)}"
                    return False, "❌ ループカットを追加してください"
            
            elif current_chapter == 4:
                # ============ CHAPTER 4 ============
                
                sphere = StageManager.find_sphere()
                
                if current_stage == 1:
                    if StageManager.is_in_sculpt_mode():
                        if sphere:
                            return True, "✓ スカルプトモード入場"
                    return False, "❌ スカルプトモードに入ってください"
                
                elif current_stage == 2:
                    if StageManager.is_in_sculpt_mode() and sphere:
                        try:
                            moved, total_dist = StageManager.get_vertex_deformation_amount(sphere, props.initial_vertex_positions)
                            
                            if moved > 5:
                                return True, f"✓ Draw ブラシで変形: {moved}頂点"
                            return False, f"❌ Draw ブラシで球を変形 ({moved}頂点)"
                        except Exception as e:
                            print(f"Error in stage 2: {e}")
                            return False, f"❌ エラー: {str(e)}"
                    return False, "❌ スカルプトモード必須"
                
                elif current_stage == 3:
                    if StageManager.is_in_sculpt_mode():
                        try:
                            brush_name = StageManager.get_current_brush_name()
                            if StageManager.is_brush_type_selected("Smooth"):
                                return True, f"✓ Smooth ブラシを選択しました ({brush_name})"
                            else:
                                current_brush = brush_name if brush_name else "未選択"
                                return False, f"❌ Smooth ブラシを選択してください (現在: {current_brush})"
                        except Exception as e:
                            print(f"Error in stage 3: {e}")
                            return False, f"❌ エラー: {str(e)}"
                    return False, "❌ スカルプトモード必須"
                
                elif current_stage == 4:
                    if StageManager.is_in_sculpt_mode():
                        try:
                            brush_name = StageManager.get_current_brush_name()
                            if StageManager.is_brush_type_selected("Grab"):
                                return True, f"✓ Grab ブラシを選択しました ({brush_name})"
                            else:
                                current_brush = brush_name if brush_name else "未選択"
                                return False, f"❌ Grab ブラシを選択してください (現在: {current_brush})"
                        except Exception as e:
                            print(f"Error in stage 4: {e}")
                            return False, f"❌ エラー: {str(e)}"
                    return False, "❌ スカルプトモード必須"
            
            elif current_chapter == 5:
                # ============ CHAPTER 5: MATERIALS ============
                
                if current_stage == 1:
                    # Stage 1: Material exists + use_nodes
                    if obj:
                        material = StageManager.get_active_material(obj)
                        if material and material.use_nodes:
                            return True, f"✓ マテリアル作成完了"
                        return False, "❌ マテリアルを作成してください"
                    return False, "❌ オブジェクトを選択してください"
                
                elif current_stage == 2:
                    # Stage 2: BaseColor != default
                    if obj:
                        material = StageManager.get_active_material(obj)
                        if material:
                            bsdf = StageManager.get_principled_bsdf(material)
                            if bsdf:
                                try:
                                    base_color = bsdf.inputs['Base Color'].default_value
                                    default = (1.0, 1.0, 1.0, 1.0)
                                    
                                    changed = any(abs(base_color[i] - default[i]) > 0.01 for i in range(4))
                                    
                                    if changed:
                                        return True, f"✓ ベースカラーを変更しました: RGB({base_color[0]:.2f}, {base_color[1]:.2f}, {base_color[2]:.2f})"
                                    return False, "❌ Base Color を変更してください"
                                except Exception as e:
                                    print(f"Error getting base color: {e}")
                                    return False, f"❌ エラー: {str(e)}"
                            return False, "❌ Principled BSDF が見つかりません"
                        return False, "❌ アクティブなマテリアルがありません"
                    return False, "❌ オブジェクトを選択してください"
                
                elif current_stage == 3:
                    # Stage 3: ImageTexture node with image
                    if obj:
                        if StageManager.check_image_texture_node_exists(obj):
                            return True, f"✓ 画像テクスチャをロードしました"
                        return False, "❌ Image Texture ノードに画像をロードしてください"
                    return False, "❌ オブジェクトを選択してください"
                
                elif current_stage == 4:
                    # Stage 4: Correct node link (ImageTexture Color -> BSDF BaseColor)
                    if obj:
                        if StageManager.check_correct_node_link(obj):
                            return True, f"✓ ノードを正しく接続しました"
                        return False, "❌ ImageTexture の Color を Principled BSDF の BaseColor に接続して��ださい"
                    return False, "❌ オブジェクトを選択してください"
                
                elif current_stage == 5:
                    # Stage 5: Roughness or Metallic changed
                    if obj:
                        material = StageManager.get_active_material(obj)
                        if material:
                            bsdf = StageManager.get_principled_bsdf(material)
                            if bsdf:
                                try:
                                    roughness = bsdf.inputs['Roughness'].default_value
                                    metallic = bsdf.inputs['Metallic'].default_value
                                    
                                    default_roughness = 0.5
                                    default_metallic = 0.0
                                    
                                    roughness_changed = abs(roughness - default_roughness) > 0.01
                                    metallic_changed = abs(metallic - default_metallic) > 0.01
                                    
                                    if roughness_changed or metallic_changed:
                                        changed_params = []
                                        if roughness_changed:
                                            changed_params.append(f"Roughness: {roughness:.2f}")
                                        if metallic_changed:
                                            changed_params.append(f"Metallic: {metallic:.2f}")
                                        
                                        return True, f"✓ PBR パラメータを変更: {', '.join(changed_params)}"
                                    return False, "❌ Roughness または Metallic を変更してください"
                                except Exception as e:
                                    print(f"Error getting PBR values: {e}")
                                    return False, f"❌ エラー: {str(e)}"
                            return False, "❌ Principled BSDF が見つかりません"
                        return False, "❌ アクティブなマテリアルがありません"
                    return False, "❌ オブジェクトを選択してください"
        
        except Exception as e:
            print(f"Validation error: {e}")
            import traceback
            traceback.print_exc()
            return False, f"❌ エラー: {str(e)}"
        
        return False, "❌ 判定エラー"
    
    @staticmethod
    def check_stage(context):
        """Check and advance stage based on current conditions"""
        try:
            props = context.scene.tutorial_props
            is_complete, _ = StageManager.validate_stage(context)
            
            if is_complete and not props.stage_complete:
                props.stage_complete = True
        except Exception as e:
            print(f"Stage check error: {e}")

# =====================================================
# PROPERTIES
# =====================================================

class TUTORIAL_PG_Properties(PropertyGroup):
    current_chapter: IntProperty(default=1, min=1, max=5)
    current_stage: IntProperty(default=1, min=1, max=5)
    stage_complete: BoolProperty(default=False)
    monitoring_active: BoolProperty(default=False)
    
    initial_position: FloatVectorProperty(default=(0.0, 0.0, 0.0), size=3)
    initial_rotation: FloatVectorProperty(default=(0.0, 0.0, 0.0), size=3)
    initial_scale: FloatVectorProperty(default=(1.0, 1.0, 1.0), size=3)
    
    initial_view_distance: FloatProperty(default=0.0)
    initial_view_location: FloatVectorProperty(default=(0.0, 0.0, 0.0), size=3)
    
    initial_vertex_count: IntProperty(default=0)
    initial_edge_count: IntProperty(default=0)
    initial_face_count: IntProperty(default=0)
    
    initial_vertex_positions: CollectionProperty(type=VertexPos)
    last_check_time: FloatProperty(default=0.0)

# =====================================================
# OPERATORS
# =====================================================

class TUTORIAL_OT_setup_stage(Operator):
    bl_idname = "tutorial.setup_stage"
    bl_label = "ステージセットアップ"
    
    def execute(self, context):
        try:
            props = context.scene.tutorial_props
            current_chapter = props.current_chapter
            current_stage = props.current_stage
            
            print(f"\n{'='*50}")
            print(f"セットアップ開始: 第{current_chapter}章 ステージ{current_stage}")
            print(f"{'='*50}\n")
            
            if current_chapter == 1:
                try:
                    bpy.ops.object.select_all(action='SELECT')
                    bpy.ops.object.delete(use_global=False)
                except:
                    pass
                
                bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 0))
                cube = bpy.context.active_object
                cube.name = "Cube"
                
                cube.location = (0.0, 0.0, 0.0)
                cube.rotation_euler = (0.0, 0.0, 0.0)
                cube.scale = (1.0, 1.0, 1.0)
                
                props.initial_position = tuple(cube.location)
                props.initial_rotation = tuple(cube.rotation_euler)
                props.initial_scale = tuple(cube.scale)
                
                print(f"✓ キューブ作成・リセット\n")
            
            elif current_chapter == 2:
                space = StageManager.get_view3d_space(context)
                if space and space.region_3d:
                    region_3d = space.region_3d
                    props.initial_view_distance = region_3d.view_distance
                    props.initial_view_location = tuple(region_3d.view_location)
                    print(f"✓ ビュー初期状態を保存\n")
            
            elif current_chapter == 3:
                cube = StageManager.find_cube()
                if cube:
                    try:
                        if cube.mode == 'EDIT':
                            bpy.ops.object.mode_set(mode='OBJECT')
                    except:
                        pass
                    
                    bpy.context.view_layer.objects.active = cube
                    cube.select_set(True)
                    
                    bpy.ops.object.mode_set(mode='EDIT')
                    bpy.context.view_layer.update()
                    
                    bm = bmesh.from_edit_mesh(cube.data)
                    for v in bm.verts:
                        v.select = False
                    for e in bm.edges:
                        e.select = False
                    for f in bm.faces:
                        f.select = False
                    bmesh.update_edit_mesh(cube.data)
                    
                    verts, edges, faces = StageManager.get_mesh_element_count(cube)
                    props.initial_vertex_count = verts
                    props.initial_edge_count = edges
                    props.initial_face_count = faces
                    
                    print(f"✓ メッシュ初期状態を保存・リセット\n")
                    
                    if current_stage == 6:
                        bpy.ops.object.mode_set(mode='OBJECT')
                        try:
                            bpy.ops.object.delete(use_global=False)
                        except:
                            pass
                        
                        bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 0))
                        cube = bpy.context.active_object
                        cube.name = "Cube"
                        bpy.ops.object.mode_set(mode='EDIT')
                        bpy.context.view_layer.update()
                        
                        bm = bmesh.from_edit_mesh(cube.data)
                        for v in bm.verts:
                            v.select = False
                        for e in bm.edges:
                            e.select = False
                        for f in bm.faces:
                            f.select = False
                        bmesh.update_edit_mesh(cube.data)
                        
                        verts, edges, faces = StageManager.get_mesh_element_count(cube)
                        props.initial_vertex_count = verts
                        props.initial_edge_count = edges
                        props.initial_face_count = faces
                        
                        print(f"✓ Stage 6 メッシュをリセット\n")
            
            elif current_chapter == 4:
                try:
                    bpy.ops.object.select_all(action='SELECT')
                    bpy.ops.object.delete(use_global=False)
                except:
                    pass
                
                bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, location=(0, 0, 0))
                sphere = bpy.context.active_object
                sphere.name = "Sphere"
                
                try:
                    bpy.ops.object.mode_set(mode='SCULPT')
                except:
                    bpy.ops.object.mode_set(mode='SCULPT')
                
                bpy.context.view_layer.update()
                
                props.initial_vertex_positions.clear()
                try:
                    for v in sphere.data.vertices:
                        item = props.initial_vertex_positions.add()
                        item.co = v.co.copy()
                except:
                    pass
                
                verts, edges, faces = StageManager.get_mesh_element_count(sphere)
                props.initial_vertex_count = verts
                
                print(f"✓ UV球を作成・スカルプトモード開始\n")
                print(f"  {verts}個の頂点位置を保存\n")
            
            elif current_chapter == 5:
                # Reset to object mode and select object
                try:
                    bpy.ops.object.mode_set(mode='OBJECT')
                except:
                    pass
                
                # Find or create a cube for materials
                cube = None
                for obj in bpy.data.objects:
                    if obj.type == 'MESH':
                        cube = obj
                        break
                
                if not cube:
                    bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 0))
                    cube = bpy.context.active_object
                    cube.name = "Cube"
                
                bpy.context.view_layer.objects.active = cube
                cube.select_set(True)
                
                # ★ Stage 1: Open Shader Editor at bottom AND focus it
                if current_stage == 1:
                    StageManager.open_shader_editor_at_bottom()
                
                print(f"✓ マテリアルステージ準備完了\n")
            
            props.stage_complete = False
            props.monitoring_active = True
            
            self.report({'INFO'}, "セットアップ完了")
            print(f"🔍 監視システム起動\n")
            
            return {'FINISHED'}
        
        except Exception as e:
            print(f"Setup error: {e}")
            import traceback
            traceback.print_exc()
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}

class TUTORIAL_OT_validate_stage(Operator):
    bl_idname = "tutorial.validate_stage"
    bl_label = "確認"
    
    def execute(self, context):
        try:
            props = context.scene.tutorial_props
            current_chapter = props.current_chapter
            current_stage = props.current_stage
            
            is_complete, message = StageManager.validate_stage(context)
            
            print(f"\n{'='*50}")
            print(f"第{current_chapter}章 ステージ{current_stage}")
            print(f"{message}")
            print(f"{'='*50}\n")
            
            if is_complete:
                props.stage_complete = True
                self.report({'INFO'}, message)
            else:
                self.report({'WARNING'}, message)
            
            return {'FINISHED'}
        except Exception as e:
            print(f"Validation error: {e}")
            import traceback
            traceback.print_exc()
            self.report({'ERROR'}, f"エラー: {str(e)}")
            return {'CANCELLED'}

class TUTORIAL_OT_next_stage(Operator):
    bl_idname = "tutorial.next_stage"
    bl_label = "次へ"
    
    def execute(self, context):
        try:
            props = context.scene.tutorial_props
            
            max_stages_per_chapter = {1: 4, 2: 4, 3: 6, 4: 4, 5: 5}
            max_stages = max_stages_per_chapter.get(props.current_chapter, 4)
            
            if props.current_stage < max_stages:
                props.current_stage += 1
            elif props.current_chapter < 5:
                props.current_chapter += 1
                props.current_stage = 1
            else:
                self.report({'INFO'}, "完了!")
                return {'FINISHED'}
            
            props.stage_complete = False
            props.monitoring_active = False
            
            self.report({'INFO'}, f"第{props.current_chapter}章 ステージ{props.current_stage}")
            return {'FINISHED'}
        except Exception as e:
            print(f"Next stage error: {e}")
            import traceback
            traceback.print_exc()
            self.report({'ERROR'}, f"エラー: {str(e)}")
            return {'CANCELLED'}

class TUTORIAL_OT_reset(Operator):
    bl_idname = "tutorial.reset"
    bl_label = "リセット"
    
    def execute(self, context):
        try:
            props = context.scene.tutorial_props
            props.current_chapter = 1
            props.current_stage = 1
            props.stage_complete = False
            props.monitoring_active = False
            self.report({'INFO'}, "リセット完了")
            return {'FINISHED'}
        except Exception as e:
            print(f"Reset error: {e}")
            import traceback
            traceback.print_exc()
            self.report({'ERROR'}, f"エラー: {str(e)}")
            return {'CANCELLED'}

class TUTORIAL_OT_goto_chapter(Operator):
    bl_idname = "tutorial.goto_chapter"
    bl_label = "チャプターへ"
    chapter: IntProperty(default=1, min=1, max=5)
    
    def execute(self, context):
        try:
            props = context.scene.tutorial_props
            props.current_chapter = self.chapter
            props.current_stage = 1
            props.stage_complete = False
            props.monitoring_active = False
            self.report({'INFO'}, f"第{self.chapter}章へ移動")
            return {'FINISHED'}
        except Exception as e:
            print(f"Goto chapter error: {e}")
            import traceback
            traceback.print_exc()
            self.report({'ERROR'}, f"エラー: {str(e)}")
            return {'CANCELLED'}

class TUTORIAL_OT_monitoring(Operator):
    bl_idname = "wm.tutorial_monitoring"
    bl_label = "Tutorial Monitoring"
    _timer = None
    _last_check = 0.0
    
    def modal(self, context, event):
        if event.type == 'TIMER':
            try:
                props = context.scene.tutorial_props
                
                if not props.monitoring_active:
                    wm = context.window_manager
                    if self._timer:
                        wm.event_timer_remove(self._timer)
                    return {'FINISHED'}
                
                if StageManager.is_undo_running():
                    return {'PASS_THROUGH'}
                
                current_time = time.time()
                if current_time - self._last_check > 0.2:
                    StageManager.check_stage(context)
                    self._last_check = current_time
            
            except Exception as e:
                print(f"Modal error: {e}")
        
        return {'PASS_THROUGH'}
    
    def execute(self, context):
        try:
            wm = context.window_manager
            self._timer = wm.event_timer_add(0.1, window=context.window)
            self._last_check = time.time()
            wm.modal_handler_add(self)
            return {'RUNNING_MODAL'}
        except Exception as e:
            print(f"Monitoring error: {e}")
            import traceback
            traceback.print_exc()
            return {'CANCELLED'}

# =====================================================
# PANEL
# =====================================================

class TUTORIAL_PT_main(Panel):
    bl_label = "3DCG チュートリアル"
    bl_idname = "TUTORIAL_PT_main"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Tutorial'
    
    def draw(self, context):
        try:
            layout = self.layout
            props = context.scene.tutorial_props
            
            ch = props.current_chapter
            st = props.current_stage
            
            max_stages_per_chapter = {1: 4, 2: 4, 3: 6, 4: 4, 5: 5}
            max_stages = max_stages_per_chapter.get(ch, 4)
            
            # Chapter selection
            box = layout.box()
            box.label(text="チャプター選択")
            row = box.row(align=True)
            for i in range(1, 6):
                op = row.operator("tutorial.goto_chapter", text=f"第{i}章", depress=(ch == i))
                op.chapter = i
            
            # Stage info
            info = StageManager.get_stage_info(ch, st)
            box = layout.box()
            box.label(text=info.get('title', ''))
            box.label(text=f"ステージ {st}/{max_stages}")
            box.label(text=info.get('name', ''))
            box.separator()
            box.label(text=info.get('description', ''))
            
            # Details field (for Chapter 5)
            if info.get('details', ''):
                box.separator()
                for line in info['details'].split('\n'):
                    box.label(text=line)
            
            if info.get('control', ''):
                box.separator()
                box.label(text=f"操作: {info['control']}")
            
            # Tip
            if info.get('tip', ''):
                box.separator()
                box.label(text=info['tip'])
            
            # Status
            box.separator()
            if props.monitoring_active:
                box.label(text="状態: 監視中...")
            else:
                box.label(text="状態: 待機中")
            
            # Main buttons
            layout.separator()
            col = layout.column()
            col.scale_y = 1.2
            col.operator("tutorial.setup_stage", text="セットアップ")
            col.operator("wm.tutorial_monitoring", text="監視開始")
            col.operator("tutorial.validate_stage", text="確認")
            
            # Next button
            if props.stage_complete:
                layout.separator()
                col = layout.column()
                col.scale_y = 1.2
                col.operator("tutorial.next_stage", text="次へ")
            
            # Reset
            layout.separator()
            layout.operator("tutorial.reset", text="リセット")
        
        except Exception as e:
            layout = self.layout
            layout.label(text=f"エラー: {str(e)}")
            import traceback
            traceback.print_exc()

# =====================================================
# REGISTER
# =====================================================

classes = (
    VertexPos,
    TUTORIAL_PG_Properties,
    TUTORIAL_OT_setup_stage,
    TUTORIAL_OT_validate_stage,
    TUTORIAL_OT_next_stage,
    TUTORIAL_OT_reset,
    TUTORIAL_OT_goto_chapter,
    TUTORIAL_OT_monitoring,
    TUTORIAL_PT_main,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.tutorial_props = bpy.props.PointerProperty(type=TUTORIAL_PG_Properties)
    print("✓ 3DCG Tutorial Simulator registered (Blender 4.2)")

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.tutorial_props
    print("✓ 3DCG Tutorial Simulator unregistered")

if __name__ == "__main__":
    register()