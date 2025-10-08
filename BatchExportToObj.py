import bpy
import os
import bmesh
import hashlib
import math
import re
from pathlib import Path
from mathutils import Vector
import json
from PIL import Image

MAP_NAME = "cs_hospital"  # Nome do mapa, pode ser alterado conforme necessário
VERTEX_LIMIT = 32767  # Limite máximo de vértices para cada tile
EXPORT_FOLDER = r"D:\ExportGTA\saida\maps\cs_hospital"
VMF_PATH = r"D:\Program Files (x86)\Steam\steamapps\common\DecompiledMaps\cs_hospital_d.vmf"

def sanitize_filename(name):
    """Remove caracteres inválidos para nomes de arquivos"""
    return re.sub(r'[<>:"/\\|?*]', '_', name)

def is_parented_to_prop_dynamic(obj):
    """Verifica se o objeto ou qualquer um de seus pais é prop_dynamic."""
    parent = obj.parent
    while parent:
        if parent.name.startswith("prop_dynamic"):
            print(f"🔗 '{obj.name}' está parentado a '{parent.name}', ignorando.")
            return True
        parent = parent.parent
    return False

def is_in_view_layer(obj, layer_coll):
    """Verifica recursivamente se o objeto está em alguma collection ativa do ViewLayer."""
    if obj.name in layer_coll.collection.objects:
        return True
    for child in layer_coll.children:
        if is_in_view_layer(obj, child):
            return True
    return False

def apply_scale_safely(obj):
    if is_parented_to_prop_dynamic(obj):
        return
    if not is_in_view_layer(obj, bpy.context.view_layer.layer_collection):
        return
    if obj.hide_get():
        print(f"👀 '{obj.name}' está oculto no viewport, ignorando.")
        return
    if obj.scale == (1.0, 1.0, 1.0):
        print(f"✅ '{obj.name}' já está com escala aplicada.")
        return

    if obj.data.users > 1:
        print(f"'{obj.name}' é multi-user no datablock, fazendo single user...")
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        bpy.ops.object.make_single_user(type='SELECTED_OBJECTS', object=True, obdata=True)

    if obj.animation_data and obj.animation_data.action and obj.type == 'ARMATURE':
        scale_factor = obj.scale[0]
        print(f"📐 Aplicando escala no Armature '{obj.name}'...")
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        print(f"🎬 Ajustando keyframes com fator {scale_factor}...")
        for fcurve in obj.animation_data.action.fcurves:
            if "location" in fcurve.data_path:
                for keyframe in fcurve.keyframe_points:
                    keyframe.co[1] *= scale_factor
                    keyframe.handle_left[1] *= scale_factor
                    keyframe.handle_right[1] *= scale_factor
        print(f"✅ Animação ajustada para '{obj.name}'.")
    else:
        print(f"📐 Aplicando escala no Mesh '{obj.name}'...")
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        print(f"✅ Escala aplicada no Mesh '{obj.name}'.")

def process_prop_dynamics(objects, map_name):
    print("🔍 Procurando objetos com nome começando em 'prop_dynamic'...")
    adjusted_objects = []
    processed_mesh_hashes = set()
    processed_armature_hashes = set()
    existing_props = [o for o in bpy.data.objects if o.name.startswith(f"{map_name}")]
    prop_counter = len(existing_props)

    for obj in objects:
        #ensure_in_viewlayer(obj)
        if obj.data.users > 1:
            print(f"'{obj.name}' é multi-user no datablock, fazendo single user...")
            bpy.context.view_layer.objects.active = obj
            obj.select_set(True)
            bpy.ops.object.make_single_user(type='SELECTED_OBJECTS', object=True, obdata=True)
        if obj.type == "MESH":
            if any(m.type == 'ARMATURE' for m in obj.modifiers):
                print(f"⚠️ '{obj.name}' tem modificador Armature, ignorando.")
                continue
            h = mesh_hash(obj.data)
            if h in processed_mesh_hashes:
                print(f"♻️ '{obj.name}' é Mesh duplicada, ignorando.")
                continue
            processed_mesh_hashes.add(h)

        elif obj.type == "ARMATURE":
            h = armature_hash(obj.data)
            if h is None:
                print(f"⚠️ '{obj.name}' não pôde gerar hash, ignorando.")
                continue
            if h in processed_armature_hashes:
                print(f"♻️ '{obj.name}' é Armature duplicada, ignorando.")
                continue
            processed_armature_hashes.add(h)
            continue  # Ignorar Armatures por enquanto

        print(f"🔧 Processando '{obj.name}'...")
        apply_scale_safely(obj)
        prop_counter += 1
        #new_name = f"{map_name}_prop_{prop_counter}"
        #obj.name = new_name
        print(f"📛 Renomeado para '{obj.name}'")
        adjusted_objects.append(obj)

    print(f"✅ {len(adjusted_objects)} objetos ajustados.")
    return adjusted_objects

def split_mesh_by_vertex_limit(obj, map_name, vertex_limit=32767):
    """
    Divide o mesh em múltiplos objetos com no máximo vertex_limit vértices.
    """
    if obj.type != 'MESH':
        print(f"⚠️ '{obj.name}' não é Mesh, ignorando split.")
        return []

    print(f"🔪 Dividindo '{obj.name}' (vértices: {len(obj.data.vertices)}) com limite de {vertex_limit} vértices...")

    # Aplica transformações
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

    # Entra no modo Edit e cria BMesh
    bpy.ops.object.mode_set(mode='EDIT')
    bm = bmesh.from_edit_mesh(obj.data)
    bm.faces.ensure_lookup_table()

    part = 0
    split_objs = []

    while True:
        # Conta vértices únicos das faces ainda no objeto
        all_faces = [f for f in bm.faces if not f.hide]
        face_vertex_map = set()
        face_selection = []

        for face in all_faces:
            verts_in_face = {v.index for v in face.verts}
            if len(face_vertex_map | verts_in_face) > vertex_limit:
                break  # atingiu limite
            face_vertex_map |= verts_in_face
            face_selection.append(face)

        if not face_selection:
            break  # nada mais para separar

        # Seleciona as faces
        for f in bm.faces:
            f.select_set(False)
        for f in face_selection:
            f.select_set(True)

        # Separa as faces selecionadas
        bpy.ops.mesh.separate(type='SELECTED')
        bpy.ops.object.mode_set(mode='OBJECT')

        # Pega o novo objeto separado
        new_obj = [o for o in bpy.context.selected_objects if o != obj][0]
        new_obj.name = f"{map_name}_split_{part}"
        split_objs.append(new_obj)
        print(f"✅ Criado: {new_obj.name} com {len(new_obj.data.vertices)} vértices.")

        # Volta para o objeto original se ainda sobrou algo
        if len(obj.data.vertices) <= vertex_limit:
            break  # tudo processado

        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.mode_set(mode='EDIT')
        bm = bmesh.from_edit_mesh(obj.data)
        bm.faces.ensure_lookup_table()
        part += 1

    bpy.ops.object.mode_set(mode='OBJECT')

    return split_objs

def ensure_in_viewlayer(obj):
    """Garante que o objeto está no ViewLayer ativo"""
    if obj.name not in bpy.context.view_layer.objects:
        bpy.context.view_layer.active_layer_collection.collection.objects.link(obj)

# --- helpers ---------------------------------------------------------------

def find_first_teximage(node, seen=None):
    """Sobe a cadeia a partir de 'node' para achar o primeiro TexImage."""
    if node is None:
        return None
    if seen is None:
        seen = set()
    if node in seen:
        return None
    seen.add(node)
    if node.type == 'TEX_IMAGE' and getattr(node, "image", None):
        return node
    for inp in node.inputs:
        for l in inp.links:
            tex = find_first_teximage(l.from_node, seen)
            if tex:
                return tex
    return None

def ensure_basecolor_tex(principled, nodes, links):
    """Garante um TexImage ligado DIRETO no Base Color (para export)."""
    base_in = principled.inputs['Base Color']
    # já tem TexImage direto?
    if base_in.is_linked and base_in.links[0].from_node.type == 'TEX_IMAGE':
        return
    # se tem cadeia, tenta achar um TexImage nela e ligar direto
    if base_in.is_linked:
        tex = find_first_teximage(base_in.links[0].from_node)
        if tex:
            links.new(tex.outputs['Color'], base_in)
            return
    # fallback: qualquer TexImage do material
    candidates = [n for n in nodes if n.type == 'TEX_IMAGE' and getattr(n, "image", None)]
    if candidates:
        links.new(candidates[0].outputs['Color'], base_in)

def ensure_normalmap_chain(principled, nodes, links):
    """Garante Image -> NormalMap -> Principled.Normal (e Non-Color)."""
    n_in = principled.inputs['Normal']
    # já está ok com NORMAL_MAP?
    if n_in.is_linked and n_in.links[0].from_node.type == 'NORMAL_MAP':
        return

    tex = None
    if n_in.is_linked:
        # remove qualquer link direto que não seja NORMAL_MAP e descubra a TexImage da cadeia
        src = n_in.links[0].from_node
        tex = find_first_teximage(src)
        links.remove(n_in.links[0])  # vamos religar corretamente

    # nenhuma ligação anterior: escolha um TexImage que pareça "normal"
    if not tex:
        def is_normal_name(n):
            name = ((n.image.name if n.image else n.name) or "").lower()
            return any(k in name for k in ("normal", "_n", ".nrm", "norm", "ddn", "_nrml"))
        tex_nodes = [n for n in nodes if n.type == 'TEX_IMAGE' and getattr(n, "image", None)]
        normals = [n for n in tex_nodes if is_normal_name(n)]
        tex = normals[0] if normals else (tex_nodes[0] if tex_nodes else None)

    if not tex:
        return  # não há imagem no material — nada a fazer

    # color space correto para normal
    try:
        tex.image.colorspace_settings.name = 'Non-Color'
    except Exception:
        pass

    # cria/injeta o Normal Map node
    normal = next((n for n in nodes if n.type == 'NORMAL_MAP'), None)
    if not normal:
        normal = nodes.new(type='ShaderNodeNormalMap')
        normal.space = 'TANGENT'
        normal.location = (principled.location.x - 220, principled.location.y - 160)

    # conecta TexImage -> NormalMap -> Principled.Normal
    links.new(tex.outputs['Color'], normal.inputs['Color'])
    links.new(normal.outputs['Normal'], n_in)

# --- versão ajustada -------------------------------------------------------

def convert_to_principled_bsdf():
    print("🎯 Convertendo materiais para Principled BSDF preservando nós e preparando para export.")

    for mat in bpy.data.materials:
        if not mat or not mat.use_nodes:
            continue

        nodes = mat.node_tree.nodes
        links = mat.node_tree.links

        # garante Principled + Output
        principled = next((n for n in nodes if n.type == 'BSDF_PRINCIPLED'), None)
        if not principled:
            principled = nodes.new(type='ShaderNodeBsdfPrincipled')
            principled.location = (0, 0)
        output = next((n for n in nodes if n.type == 'OUTPUT_MATERIAL'), None)
        if not output:
            output = nodes.new(type='ShaderNodeOutputMaterial')
            output.location = (400, 0)
        if not output.inputs['Surface'].is_linked:
            links.new(principled.outputs['BSDF'], output.inputs['Surface'])

        # 1) Base Color: precisa de TexImage direto pro Sollumz
        ensure_basecolor_tex(principled, nodes, links)

        # 2) Normal: força sempre Image -> NormalMap -> Principled.Normal
        ensure_normalmap_chain(principled, nodes, links)

    print("✅ Materiais prontos: BaseColor com TexImage direto e Normal com Normal Map.")


        
def unpack_material_images(output_dir=None):
    # Pasta padrão = onde está salvo o .blend
    if not output_dir:
        output_dir = bpy.path.abspath("//textures")
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    print(f"📦 Unpacking imagens para: {output_dir}")

    for obj in bpy.data.objects:
        if obj.type != 'MESH':
            continue
        print(f"🔍 Verificando materiais em '{obj.name}'...")

        #ensure_in_viewlayer(obj)
        for slot in obj.material_slots:
            mat = slot.material
            if not mat or not mat.use_nodes:
                continue

            for node in mat.node_tree.nodes:
                if node.type == 'TEX_IMAGE' and node.image:
                    img = node.image
                    if img.packed_file:
                        print(f"📤 Unpacking '{img.name}'...")
                        # Unpack a imagem para a pasta especificada
                        img.unpack(method='USE_LOCAL')
                        # Salva no diretório de saída
                        img.filepath_raw = os.path.join(output_dir, img.name)
                        img.save()
                    else:
                        print(f"✅ '{img.name}' já está unpacked.")

    print("🎉 Todos os materiais selecionados foram processados.")

def mesh_hash(mesh, include_materials=True):
    """Gera um hash para o datablock de Mesh incluindo materiais opcionalmente."""
    if not isinstance(mesh, bpy.types.Mesh):
        return None

    # Hash dos vértices e faces (como você já fazia)
    verts = [tuple(round(c, 5) for c in v.co) for v in mesh.vertices]
    faces = [tuple(f.vertices) for f in mesh.polygons]
    data = str(verts) + str(faces)

    # Inclui materiais se necessário
    if include_materials:
        materials = [mat.name if mat else "None" for mat in mesh.materials]
        data += str(materials)

    return hashlib.md5(data.encode()).hexdigest()

def armature_hash(armature_data):
    """Hash único para estrutura e animações de uma Armature"""
    if not isinstance(armature_data, bpy.types.Armature):
        print(f"⚠️ Ignorando hash: '{armature_data}' não é Armature.")
        return None
    bones_info = []
    for bone in armature_data.bones:
        parent_name = bone.parent.name if bone.parent else "None"
        bones_info.append((bone.name, parent_name))
    for action in bpy.data.actions:
        if action.users > 0:
            bones_info.append(action.name)
    # Ordena apenas se todos são tuples
    try:
        bones_info.sort()
    except TypeError as e:
        print(f"❌ Erro ao ordenar bones_info: {e}")
        return None
    data_str = str(bones_info)
    return hashlib.md5(data_str.encode()).hexdigest()

def merge_static_props(static_props):
    bpy.ops.object.select_all(action='DESELECT')
    print("🔍 Fazendo fusão de static props...")

    for obj in static_props:
        obj.select_set(True)

    bpy.context.view_layer.objects.active = static_props[0]
    if len(static_props) > 1:
        print("🔗 Fazendo merge...")
        bpy.ops.object.join()
        merged_obj = bpy.context.active_object
    else:
        print("✅ Apenas 1 static prop encontrado.")
        merged_obj = static_props[0]

    # 🔥 Só aplica transformações aqui
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

    merged_obj.name = f"{MAP_NAME}_merged"
    print(f"🏁 Objeto final pronto: '{merged_obj.name}'")
    return merged_obj



def is_mesh_linked_to_armature(obj):
    """Verifica se o Mesh está parentado a uma Armature ou tem Armature Modifier"""
    if obj.type != 'MESH':
        return False
    # Parent direto
    if obj.parent and obj.parent.type == 'ARMATURE':
        return True
    # Modificador Armature
    if any(mod.type == 'ARMATURE' for mod in obj.modifiers):
        return True
    return False

def clean_filename(name):
    """
    Limpa o nome para exportação:
    - Substitui / e \ por _
    - Remove caracteres problemáticos (:, ~)
    - Remove extensões .mdl e .smd
    """
    cleaned = name.replace("\\", "_").replace("/", "_").replace(":", "_").replace("~", "")
    cleaned = cleaned.replace(".mdl", "").replace(".smd", "")
    return cleaned


def get_model_name(obj, map_name="map"):
    """
    Retorna o nome limpo do modelo:
    - Usa path_id se existir
    - Caso contrário, usa obj.name
    - Garante prefixo MAP_NAME
    """
    if not isinstance(obj, bpy.types.Object):
        print(f"⚠️ Esperava objeto Blender, mas recebeu {type(obj)}: {obj}")
        return f"{map_name}_unknown_object"

    # Tenta pegar o path_id
    if "path_id" in obj:
        path = obj["path_id"]
        model_name = clean_filename(path)
    else:
        model_name = clean_filename(obj.name)

    # Garante que comece com MAP_NAME_
    if not model_name.startswith(f"{map_name}_"):
        model_name = f"{map_name}_{model_name}"

    return model_name


def create_dummy_texture(texture_dir, dummy_name="dummy_transparent.png"):
    """Cria uma imagem PNG 1x1 transparente se não existir"""
    dummy_path = os.path.join(texture_dir, dummy_name)
    if not os.path.exists(dummy_path):
        img = bpy.data.images.new(name=dummy_name, width=1, height=1, alpha=True)
        img.generated_color = (0, 0, 0, 0)  # Transparente
        img.filepath_raw = dummy_path
        img.file_format = 'PNG'
        img.save()
        print(f"🖼️ Dummy texture criada: {dummy_path}")
    else:
        print(f"🖼️ Dummy texture já existe: {dummy_path}")
    return dummy_path

def apply_dummy_to_materials(texture_dir):
    """Aplica uma textura dummy a todos os materiais sem textura de arquivo"""
    dummy_path = create_dummy_texture(texture_dir)

    for mat in bpy.data.materials:
        if not mat.use_nodes:
            mat.use_nodes = True

        nodes = mat.node_tree.nodes
        links = mat.node_tree.links

        # Verifica se já existe node de textura com arquivo válido
        has_texture_file = False
        for node in nodes:
            if node.type == 'TEX_IMAGE' and node.image and node.image.filepath:
                if os.path.isfile(bpy.path.abspath(node.image.filepath)):
                    has_texture_file = True
                    break

        if has_texture_file:
            print(f"✅ '{mat.name}' já tem textura de arquivo, ignorado.")
            continue  # Não sobrescreve materiais com textura real

        print(f"⚠️ '{mat.name}' sem textura, aplicando dummy.")

        # Cria node de textura se não existir
        tex_node = nodes.get("Dummy_Texture")
        if not tex_node:
            tex_node = nodes.new(type='ShaderNodeTexImage')
            tex_node.name = "Dummy_Texture"
            tex_node.label = "Dummy Texture"
            tex_node.image = bpy.data.images.load(dummy_path)

        # Conecta à entrada Base Color do Principled BSDF
        principled_node = next((n for n in nodes if n.type == 'BSDF_PRINCIPLED'), None)
        if not principled_node:
            principled_node = nodes.new(type='ShaderNodeBsdfPrincipled')
            principled_node.location = (0, 0)

        # Reconecta textura ao Principled BSDF
        links.new(tex_node.outputs['Color'], principled_node.inputs['Base Color'])

        # Garante saída para Material Output
        output_node = next((n for n in nodes if n.type == 'OUTPUT_MATERIAL'), None)
        if not output_node:
            output_node = nodes.new(type='ShaderNodeOutputMaterial')
            output_node.location = (400, 0)
        links.new(principled_node.outputs['BSDF'], output_node.inputs['Surface'])

    print("🎨 Todos os materiais sem textura receberam dummy.")

def center_geometry_to_origin(obj):
    """
    Move a geometria para que o origin do objeto seja o centro da geometria.
    """
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    # Move o origin para o centro da geometria
    bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='BOUNDS')
    # E move a geometria para que fique em torno do origin
    bpy.ops.object.transform_apply(location=True, rotation=False, scale=False)
    print(f"📍 Origin centralizado em '{obj.name}'")

def parse_vmf_and_mark_parented(vmf_path):
    """
    Lê o arquivo .vmf, encontra todas as entidades com parentname
    e aplica a propriedade custom 'is_parented' nos objetos da cena Blender.
    """
    print(f"🔍 Lendo VMF: {vmf_path}")
    parented_entities = {}

    with open(vmf_path, 'r', encoding='utf-8') as vmf_file:
        content = vmf_file.read()

    # Regex para capturar blocos de entidades
    entity_blocks = re.findall(r'entity\s*\{([^}]*)\}', content, re.MULTILINE | re.DOTALL)

    for block in entity_blocks:
        classname_match = re.search(r'"classname"\s+"([^"]+)"', block, re.IGNORECASE)
        id_match = re.search(r'"id"\s+"([^"]+)"', block, re.IGNORECASE)
        parentname_match = re.search(r'"parentname"\s+"([^"]+)"', block, re.IGNORECASE)

        if classname_match and id_match and parentname_match:
            classname = classname_match.group(1)
            entity_id = id_match.group(1)
            parentname = parentname_match.group(1)
            key = f"{classname}_{entity_id}"
            parented_entities[key] = parentname
            print(f"📦 Encontrado: {key} → parent: {parentname}")

    print(f"✅ Total de entidades com parentname: {len(parented_entities)}")

    # Marca no Blender os objetos encontrados
    for obj in bpy.data.objects:
        if obj.name in parented_entities:
            obj["is_parented"] = True
            print(f"🔗 '{obj.name}' marcado como parented.")

    return parented_entities

# 📂 Caminho do arquivo JSON de saída
output_path = bpy.path.abspath("D:/Blender/Maps/cs_hospital.json")

# 📦 Lista para armazenar os triggers
triggers = []

# 🔥 Itera sobre todos os objetos da cena
for obj in bpy.context.scene.objects:
    if obj.type != 'MESH':
        continue  # Ignora não-meshes

    # 🏷️ Pega o nome e separa por "_"
    name_parts = obj.name.split("_")
    if len(name_parts) < 2:
        print(f"⚠️ Ignorando {obj.name}, formato inválido")
        continue

    classname = name_parts[0]
    id_value = name_parts[1]

    # 📏 Bounding Box: calcula tamanho e centro
    bbox_corners = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    min_x = min(corner.x for corner in bbox_corners)
    max_x = max(corner.x for corner in bbox_corners)
    min_y = min(corner.y for corner in bbox_corners)
    max_y = max(corner.y for corner in bbox_corners)
    min_z = min(corner.z for corner in bbox_corners)
    max_z = max(corner.z for corner in bbox_corners)

    center = [
        round((min_x + max_x) / 2, 4),
        round((min_y + max_y) / 2, 4),
        round((min_z + max_z) / 2, 4)
    ]
    size = [
        round(max_x - min_x, 4),
        round(max_y - min_y, 4),
        round(max_z - min_z, 4)
    ]

    # 📦 Adiciona dados ao trigger
    triggers.append({
        "classname": classname,
        "id": id_value,
        "position": center,
        "bbox": size
    })

# 💾 Salva como JSON
with open(output_path, 'w') as f:
    json.dump(triggers, f, indent=4)
    print(f"✅ Exportado {len(triggers)} triggers para {output_path}")

def create_transparent_texture(filepath, size=4):
    """Cria uma textura PNG totalmente transparente"""
    from PIL import Image
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    img.save(filepath)
    print(f"✅ Textura transparente criada em {filepath}")
    
output_texture_path = bpy.path.abspath("//transparent_material.png")
def convert_invisible_materials_to_principled():
    """Detecta materiais totalmente invisíveis e converte para Principled BSDF com alpha 0"""
    # Garante que a textura transparente exista
    if not os.path.exists(output_texture_path):
        create_transparent_texture(output_texture_path)

    for mat in bpy.data.materials:
        if not mat.use_nodes:
            continue

        nodes = mat.node_tree.nodes
        links = mat.node_tree.links
        output_node = next((n for n in nodes if n.type == 'OUTPUT_MATERIAL'), None)
        if not output_node:
            continue  # Nenhum Output Material? Ignora

        # 🔥 Verifica se o shader final é 100% transparente
        invisible = False

        for link in output_node.inputs['Surface'].links:
            from_node = link.from_node

            # Principled com Alpha == 0 e não conectado ao Alpha
            if from_node.type == 'BSDF_PRINCIPLED':
                alpha_socket = from_node.inputs['Alpha']
                if not alpha_socket.is_linked and alpha_socket.default_value == 0.0:
                    invisible = True
                    print(f"🕳️ {mat.name} é invisível (Principled Alpha=0)")

            # Transparent BSDF diretamente ligado
            elif from_node.type == 'BSDF_TRANSPARENT':
                invisible = True
                print(f"🕳️ {mat.name} é invisível (Transparent BSDF direto)")

            # Mix Shader com fator 1.0 para Transparent
            elif from_node.type == 'MIX_SHADER':
                fac = from_node.inputs['Fac'].default_value
                if fac == 1.0:
                    linked_shader = None
                    for inp in from_node.inputs:
                        if inp.is_linked:
                            linked_shader = inp.links[0].from_node
                            if linked_shader.type == 'BSDF_TRANSPARENT':
                                invisible = True
                                print(f"🕳️ {mat.name} é invisível (Mix Shader totalmente transparente)")

        if invisible:
            print(f"🎯 Convertendo material invisível: {mat.name}")

            # Limpa nodes antigos
            nodes.clear()

            # Cria novos nodes
            principled = nodes.new(type='ShaderNodeBsdfPrincipled')
            output = nodes.new(type='ShaderNodeOutputMaterial')
            tex_image = nodes.new(type='ShaderNodeTexImage')

            tex_image.image = bpy.data.images.load(output_texture_path)
            tex_image.interpolation = 'Closest'

            # Configura Principled BSDF com alpha 0
            principled.inputs['Alpha'].default_value = 0.0
            principled.inputs['Base Color'].default_value = (0, 0, 0, 0)

            # Liga os nodes
            links.new(tex_image.outputs['Color'], principled.inputs['Base Color'])
            links.new(principled.outputs['BSDF'], output.inputs['Surface'])

def process_everything():
    print("🚀 Iniciando pipeline...")
    parse_vmf_and_mark_parented(VMF_PATH)
    
    unpack_material_images()
    convert_to_principled_bsdf()
    convert_invisible_materials_to_principled()
    #apply_dummy_to_materials("//textures")


    static_props = []
    dynamic_props = []
    processed_hashes = {}
    export_queue = []
    
    redirect_models = {}  # 👈 Adiciona tabela de redirecionamento

    # Coleta objetos
    for obj in bpy.data.objects:
        # 📦 Está relacionado à geometria estática
        if (obj.name.startswith("func_detail") or
            obj.name.startswith("overlay") or
            obj.name.startswith("prop_static") or
            obj.name.startswith("worldspawn") or
            obj.name.startswith("func_brush") or
            obj.name.startswith("prop_dynamic") or
            obj.name.startswith("prop_physics") or
            obj.name.startswith("func_illusionary") or
            obj.name.startswith("func_rotating") or
            obj.name.startswith("func_door") or
            obj.name.startswith("func_button")) and obj.type == 'MESH':
            #if "is_parented" in obj:
            #    dynamic_props.append(obj)
            #else:
                static_props.append(obj)

        # 🚀 Dinâmicos (não ligados a Armature)
        #elif (obj.name.startswith("prop_dynamic") or
        #        #obj.name.startswith("worldspawn") or
        #        obj.name.startswith("func_breakable") or
        #        obj.name.startswith("func_movelinear") or
        #        obj.name.startswith("func_tracktrain") or
        #        obj.name.startswith("func_door") or
        #        obj.name.startswith("func_brush") or
        #        obj.name.startswith("prop_physics_override") or
        #        obj.name.startswith("func_ladder") or
        #        obj.name.startswith("func_rotating") or
        #        obj.name.startswith("func_wall_toggle") or
        #        obj.name.startswith("func_physbox")):
        #    if obj.type == 'MESH' and not is_mesh_linked_to_armature(obj):
        #        dynamic_props.append(obj)

    # 🟩 Processa estáticos
    num_splits = 0
    if static_props:
        print(f"📦 {len(static_props)} static props encontrados.")
        merged_static = merge_static_props(static_props)
        split_objs = split_mesh_by_vertex_limit(merged_static, MAP_NAME, vertex_limit=VERTEX_LIMIT)
        
        num_splits = len(split_objs)
        for obj in split_objs:
            if "path_id" in obj:
                print(f"🗑️ Removendo 'path_id' de '{obj.name}'")
                del obj["path_id"]
        export_queue += split_objs
    
    #convert_invisible_materials_to_principled()
    #apply_dummy_to_materials("//textures")
    #convert_to_principled_bsdf()
    # 🟥 Processa dinâmicos
    if dynamic_props:
        print(f"📦 {len(dynamic_props)} dynamic props encontrados.")
        for obj in dynamic_props:
            bpy.context.view_layer.objects.active = obj
            bpy.ops.object.select_all(action='DESELECT')
            obj.select_set(True)
            bpy.ops.object.duplicate()
            dup_obj = bpy.context.active_object

            if not dup_obj:
                raise RuntimeError(f"❌ Falha ao duplicar '{obj.name}'")
            
            dup_obj.name = f"{dup_obj.name}_export"

            if "path_id" not in obj:# and not obj.name.startswith("worldspawn"):
                bpy.ops.object.select_all(action='DESELECT')
                dup_obj.select_set(True)
                bpy.context.view_layer.objects.active = dup_obj
                bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

                # Move origin para o world origin
                bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='BOUNDS')
                bpy.ops.object.location_clear()
                bpy.ops.object.rotation_clear()
                bpy.ops.object.scale_clear()

                # Entra no modo Edit
                bpy.ops.object.mode_set(mode='EDIT')
                bm = bmesh.from_edit_mesh(dup_obj.data)

                # Calcula offset dos vértices
                offset = dup_obj.location
                for v in bm.verts:
                    v.co -= offset

                bmesh.update_edit_mesh(dup_obj.data)
                bpy.ops.object.mode_set(mode='OBJECT')

                # Aplica transformações para fixar a geometria no centro
                bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
            else:
                # Apenas aplica escala
                bpy.ops.object.select_all(action='DESELECT')
                dup_obj.select_set(True)
                bpy.context.view_layer.objects.active = dup_obj
                bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
                
            # Define key para evitar duplicatas
            key = dup_obj.get("path_id", mesh_hash(dup_obj.data))
            redirect_key = f"{obj.name}"  # 👈 Sempre classname_id

            if key in processed_hashes:
                # 👇 Salva redirecionamento se objeto duplicado
                redirect_models[redirect_key] = processed_hashes[key]
                print(f"♻️ '{dup_obj.name}' duplicado (key: {key}), redirect para '{processed_hashes[key]}'")
                bpy.data.objects.remove(dup_obj)
                continue
            
            processed_hashes[key] = get_model_name(obj, map_name=MAP_NAME)
            redirect_models[redirect_key] = processed_hashes[key]
            export_queue.append(dup_obj)


    # 📤 Exportação .obj
    print(f"📦 Exportando {len(export_queue)} objetos para .obj...")
    for obj in export_queue:
        model_name = get_model_name(obj, map_name=MAP_NAME)
        obj.name = model_name
        filename = f"{model_name}.obj"
        filepath = os.path.join(EXPORT_FOLDER, filename)
        print(f"📤 Exportando '{obj.name}' como '{filename}'")

        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        bpy.ops.wm.obj_export(
            filepath=filepath,
            export_selected_objects=True,
            forward_axis='NEGATIVE_Z',
            up_axis='Y',
            export_materials=True,  # <--- ATIVAR exportação de materiais
            path_mode='COPY',       # Copia as texturas para o diretório de exportação
        )

    # 📝 Gera metadata.json
    metadata = {
        "map_name": MAP_NAME,
        "num_splits": num_splits,
        "redirect_models": redirect_models
    }
    metadata_path = os.path.join(EXPORT_FOLDER, f"{MAP_NAME}_metadata.json")
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=4)
    print(f"📄 Metadata salvo em: {metadata_path}")

    print("🎉 Pipeline de exportação concluído.")
    
process_everything()