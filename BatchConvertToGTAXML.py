import bpy
import os
import bgl
import gpu
from gpu_extras.batch import batch_for_shader
from PIL import Image
import os

# 📁 Caminho da pasta de entrada e saída
input_folder = r"D:\ExportGTA\saida\maps\cs_hospital"
output_folder = r"D:\ExportGTA\saida\maps\cs_hospital_output"
os.makedirs(output_folder, exist_ok=True)

def create_transparent_texture(filepath, size=4):
    """Cria uma textura PNG totalmente transparente"""
    from PIL import Image
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    img.save(filepath)
    print(f"✅ Textura transparente criada em {filepath}")

def convert_to_principled_bsdf():
    print("🎯 Convertendo materiais para Principled BSDF...")

    for obj in bpy.data.objects:
        if obj.type != 'MESH':
            continue

        #ensure_in_viewlayer(obj)

        print(f"🔍 Verificando materiais de '{obj.name}'...")
        for slot in obj.material_slots:
            mat = slot.material
            if not mat:
                continue

            if not mat.use_nodes:
                mat.use_nodes = True

            nodes = mat.node_tree.nodes
            links = mat.node_tree.links

            # Se node_tree estiver vazio, cria básico
            if not nodes:
                print(f"➕ '{mat.name}' sem nodes. Criando Principled básico...")
                principled = nodes.new(type='ShaderNodeBsdfPrincipled')
                output_node = nodes.new(type='ShaderNodeOutputMaterial')
                links.new(principled.outputs['BSDF'], output_node.inputs['Surface'])
                continue

            # Verifica Principled BSDF
            principled = next((n for n in nodes if n.type == 'BSDF_PRINCIPLED'), None)

            if not principled:
                print(f"➕ '{mat.name}' não usa Principled BSDF. Criando...")
                # Limpa antigos shaders
                for node in nodes:
                    if node.type.startswith('BSDF') or node.type in {'EMISSION', 'DIFFUSE', 'NORMAL_MAP'}:
                        nodes.remove(node)
                principled = nodes.new(type='ShaderNodeBsdfPrincipled')
                principled.location = (0, 0)

                # Conecta ao Output
                output_node = next((n for n in nodes if n.type == 'OUTPUT_MATERIAL'), None)
                if not output_node:
                    output_node = nodes.new(type='ShaderNodeOutputMaterial')
                    output_node.location = (400, 0)
                links.new(principled.outputs['BSDF'], output_node.inputs['Surface'])

            # Reconectar Texturas
            for node in nodes:
                if node.type == 'TEX_IMAGE' and node.image:
                    tex_name = node.label or node.name
                    if "normal" in tex_name.lower():
                        print(f"🔗 Reconectando Normal Map '{tex_name}'")
                        # Remove NormalMap antigos
                        for n in nodes:
                            if n.type == 'NORMAL_MAP':
                                nodes.remove(n)
                        normal_map = nodes.new(type='ShaderNodeNormalMap')
                        normal_map.location = (-300, -300)
                        links.new(node.outputs['Color'], normal_map.inputs['Color'])
                        links.new(normal_map.outputs['Normal'], principled.inputs['Normal'])
                    else:
                        print(f"🎨 Reconectando Base Color '{tex_name}'")
                        links.new(node.outputs['Color'], principled.inputs['Base Color'])

    print("✅ Todos os materiais agora usam Principled BSDF.")
    
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

def object_has_partial_transparency(obj):
    """Detecta se o objeto tem materiais com transparência real"""
    for slot in obj.material_slots:
        mat = slot.material
        if not mat or not mat.use_nodes:
            continue

        nodes = mat.node_tree.nodes
        links = mat.node_tree.links

        # 🚩 Verifica se o blend_method já indica transparência
        if mat.blend_method in {'BLEND', 'HASHED', 'CLIP'}:
            print(f"⚠️ {obj.name} usa {mat.name} com blend_method {mat.blend_method}")
            return True

        # 🚩 Verifica conexões de Alpha no Principled BSDF
        for node in nodes:
            if node.type == 'BSDF_PRINCIPLED':
                alpha_input = node.inputs['Alpha']
                if alpha_input.is_linked:
                    print(f"⚠️ {obj.name} usa {mat.name} com Alpha conectado")
                    return True

            # 🚩 Verifica se Transparent BSDF está conectado ao Output
            if node.type == 'BSDF_TRANSPARENT':
                for link in node.outputs['BSDF'].links:
                    target = link.to_node
                    if target.type == 'MIX_SHADER':
                        print(f"⚠️ {obj.name} usa {mat.name} com Transparent BSDF + Mix Shader")
                        return True

            # 🚩 Verifica se textura RGBA está ligada em algo
            if node.type == 'TEX_IMAGE' and node.image and node.image.depth == 32:
                # Checa se a saída Alpha está conectada
                if node.outputs['Alpha'].is_linked:
                    print(f"⚠️ {obj.name} usa {mat.name} com textura RGBA ({node.image.name}) Alpha ligado")
                    return True

    # Nenhum sinal de transparência real
    return False

def is_material_transparent(mat):
    """Detecta se o material tem transparência real"""
    if not mat or not mat.use_nodes:
        return False

    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    output_node = next((n for n in nodes if n.type == 'OUTPUT_MATERIAL'), None)
    if not output_node:
        return False

    for link in output_node.inputs['Surface'].links:
        from_node = link.from_node

        # Principled BSDF com Alpha conectado
        if from_node.type == 'BSDF_PRINCIPLED':
            alpha_socket = from_node.inputs['Alpha']
            if alpha_socket.is_linked:
                return True

        # Transparent BSDF diretamente conectado
        if from_node.type == 'BSDF_TRANSPARENT':
            return True

        # Mix Shader com Transparent BSDF
        if from_node.type == 'MIX_SHADER':
            for input_socket in from_node.inputs:
                if input_socket.is_linked:
                    linked_node = input_socket.links[0].from_node
                    if linked_node.type == 'BSDF_TRANSPARENT':
                        return True

        # Textura RGBA com Alpha ligado
        if from_node.type == 'TEX_IMAGE' and from_node.image and from_node.image.depth == 32:
            if from_node.outputs['Alpha'].is_linked:
                return True

    return False


def image_has_transparency(filepath):
    """Analisa o canal alpha do arquivo de imagem"""
    if not os.path.isfile(filepath):
        print(f"❌ Arquivo não encontrado: {filepath}")
        return False

    try:
        with Image.open(filepath) as img:
            if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
                alpha = img.getchannel("A")
                extrema = alpha.getextrema()
                if extrema[0] < 255:
                    print(f"⚠️ {os.path.basename(filepath)} tem transparência (Alpha extrema: {extrema})")
                    return True
                else:
                    print(f"✅ {os.path.basename(filepath)} é opaco (Alpha extrema: {extrema})")
                    return False
            else:
                print(f"✅ {os.path.basename(filepath)} sem canal alpha (mode={img.mode})")
                return False
    except Exception as e:
        print(f"❌ Erro ao abrir {filepath}: {e}")
        return False


def image_has_transparency(filepath):
    """Analisa o canal alpha do arquivo de imagem"""
    if not os.path.isfile(filepath):
        print(f"❌ Arquivo não encontrado: {filepath}")
        return False

    try:
        with Image.open(filepath) as img:
            if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
                alpha = img.getchannel("A")
                extrema = alpha.getextrema()
                if extrema[0] < 255:
                    print(f"⚠️ {os.path.basename(filepath)} tem transparência (Alpha extrema: {extrema})")
                    return True
                else:
                    print(f"✅ {os.path.basename(filepath)} é opaco (Alpha extrema: {extrema})")
                    return False
            else:
                print(f"✅ {os.path.basename(filepath)} sem canal alpha (mode={img.mode})")
                return False
    except Exception as e:
        print(f"❌ Erro ao abrir {filepath}: {e}")
        return False


def convert_materials_with_alpha_flags(obj):
    """Converte materiais individualmente com Alpha flag se necessário"""
    wm = bpy.data.window_managers["WinMan"]

    print(f"🎯 Processando materiais do objeto '{obj.name}'...")
    for i, slot in enumerate(obj.material_slots):
        mat = slot.material
        if not mat:
            continue

        print(f"🔍 Verificando material '{mat.name}'...")

        has_alpha = False

        if mat.use_nodes:
            # Procura texture node com imagem
            for node in mat.node_tree.nodes:
                if node.type == 'TEX_IMAGE' and node.image:
                    image_path = bpy.path.abspath(node.image.filepath)
                    print(f"📂 Verificando textura: {image_path}")
                    has_alpha = image_has_transparency(image_path)
                    if has_alpha:
                        break

        if has_alpha:
            print(f"⚠️ '{mat.name}' usa textura com transparência → Aplicando Alpha flag")
            wm.sz_shader_material_index = 139 #2  # Alpha
        else:
            print(f"✅ '{mat.name}' sem transparência → Aplicando Opaque flag")
            wm.sz_shader_material_index = 0  # Opaque

        # Seleciona material no slot atual
        obj.active_material_index = i

        # Converte somente este material
        bpy.ops.sollumz.convertmaterialtoselected()

    print(f"✅ Materiais de '{obj.name}' processados.")

def process_sollumz_drawable_and_collision(obj):
    #convert_invisible_materials_to_principled()
    #apply_dummy_to_materials("//textures")
    #convert_to_principled_bsdf()
    #hasTransparency = object_has_partial_transparency(obj)
    print(f"🎯 Processando '{obj.name}' para exportação...")
    if obj.name.endswith("_export"):
        old_name = obj.name
        new_name = obj.name.removesuffix("_export")
        obj.name = new_name
        print(f"🔄 Renomeado: {old_name} → {new_name}")
        
    original_name = obj.name
    
    wm = bpy.data.window_managers["WinMan"]
    #wm.sz_shader_material_index = 0
    wm.sz_collision_material_index = 0
    #if hasTransparency:
    #    bpy.data.window_managers["WinMan"].sz_shader_material_index = 2

    # Duplica para colisão
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    bpy.ops.object.duplicate()
    collision_obj = bpy.context.active_object
    collision_obj.name = f"{original_name}_Collision"

    if not collision_obj.data or not collision_obj.data.polygons:
        print(f"❌ '{collision_obj.name}' não tem faces. Ignorando colisão.")
        bpy.data.objects.remove(collision_obj)
        return

    bpy.ops.object.select_all(action='DESELECT')
    collision_obj.sollum_type = 'sollumz_bound_poly_triangle'
    bpy.context.view_layer.objects.active = collision_obj
    collision_obj.select_set(True)
    bpy.ops.sollumz.clearandcreatecollisionmaterial()
    print(f"✅ Colisão configurada para '{collision_obj.name}'.")

    # Converte mesh visual
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    obj.sollum_type = 'sollumz_drawable_model'
    obj.name = f"{original_name}_Model"
    #bpy.ops.sollumz.convertallmaterialstoselected()
    #bpy.ops.sollumz.convertmaterialtoselected()
    convert_materials_with_alpha_flags(obj)
    
    bpy.ops.sollumz.uv_maps_rename_by_order()
    bpy.ops.sollumz.color_attrs_add_missing()
    bpy.ops.sollumz.setallmatembedded()
    bpy.ops.sollumz.setallembedded()

    bpy.ops.sollumz.converttodrawable()

    drawable_empty = obj.parent
    drawable_empty.name = original_name
    if drawable_empty and drawable_empty.sollum_type == 'sollumz_drawable':
        print(f"📦 Drawable criado: {drawable_empty.name}")
    else:
        print("❌ Drawable Empty não encontrado após conversão!")
        return

    # Converte colisão em Composite
    collision_obj.parent = drawable_empty
    bpy.ops.object.select_all(action='DESELECT')
    collision_obj.select_set(True)
    bpy.context.view_layer.objects.active = collision_obj
    bpy.ops.sollumz.converttocomposite()
    #bound_geometrybvh = collision_obj.parent
    #bound_composite = bound_geometrybvh.parent
    #bound_composite.parent = drawable_empty

    print(f"✅ Hierarquia completa:")
    print(f"    Drawable → {drawable_empty.name}")
    print(f"    Colisão → {collision_obj.name}")

def clear_scene():
    """Limpa todos os objetos da cena atual"""
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    print("🧹 Cena limpa.")

def load_obj(filepath):
    """Importa um arquivo OBJ"""
    print(f"📥 Importando: {filepath}")
    bpy.ops.wm.obj_import(filepath=filepath, forward_axis='NEGATIVE_Z', up_axis='Y')

def save_as_gta(filepath):
    """Exporta o objeto processado como YDR/YBN/YDD usando Sollumz (placeholder)"""
    print(f"📤 Exportando para GTA: {filepath}")
    # Substitua abaixo com a função real do Sollumz
    bpy.ops.sollumz.export_assets(directory=output_folder)

def process_obj(obj):
    """Aqui você define o processamento com Sollumz"""
    print(f"⚙️ Processando: {obj.name}")
    # Exemplo: chama sua função personalizada
    process_sollumz_drawable_and_collision(obj)

def batch_process_objs():
    """Carrega e processa todos os .obj da pasta"""
    obj_files = [f for f in os.listdir(input_folder) if f.lower().endswith('.obj')]
    if not obj_files:
        print("❌ Nenhum arquivo .obj encontrado na pasta.")
        return

    print(f"🔄 Iniciando processamento de {len(obj_files)} arquivos...")
    for i, filename in enumerate(obj_files, start=1):
        print(f"\n📦 [{i}/{len(obj_files)}] Processando: {filename}")
        filepath = os.path.join(input_folder, filename)

        # Limpa a cena
        clear_scene()

        # Importa o OBJ
        load_obj(filepath)

        # Assume que o objeto importado é o primeiro Mesh encontrado
        imported_objs = [obj for obj in bpy.context.scene.objects if obj.type == 'MESH']
        if not imported_objs:
            print(f"⚠️ Nenhum objeto Mesh encontrado em {filename}. Ignorando.")
            continue

        obj = imported_objs[0]  # Apenas o primeiro Mesh
        process_obj(obj)

        # Exporta o resultado para pasta de saída
        out_filename = os.path.splitext(filename)[0] + "_gta.obj"  # ou .ydr/.ybn
        out_filepath = os.path.join(output_folder, out_filename)
        save_as_gta(out_filepath)

    print("\n✅ Todos os arquivos processados.")

# 🚀 Executa
if __name__ == "__main__":
    batch_process_objs()
