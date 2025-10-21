import bpy, bmesh, math, random, sys, os
from mathutils import Vector, Matrix
from PIL import Image
import json

# Caminho do Sollumz
sollumz_path = r"C:\Users\vigus\AppData\Roaming\Blender Foundation\Blender\4.3\extensions\user_default"

if sollumz_path not in sys.path:
    sys.path.append(sollumz_path)
    print(f"📦 Caminho do Sollumz adicionado: {sollumz_path}")
else:
    print("✅ Caminho do Sollumz já presente.")

# =========================
# CLI ARGS (opcional)
# =========================
def get_arg(k, default=None, cast=str):
    for a in sys.argv:
        if a.startswith("--" + k + "=") or a.startswith(k + "="):
            try:
                v = a.split("=", 1)[1].strip().strip('"').strip("'")
                return cast(v)
            except Exception:
                return default
    return default



MAP_NAME = get_arg("MAP_NAME", "tracks", str)
# raiz padrão (pode vir do argumento OUTPUT_PATH)
OUTPUT_ROOT = os.path.abspath("D:/TrackGen/output/" + MAP_NAME)
OUTPUT_PATH = os.path.join(OUTPUT_ROOT, "track_data.json")
OUTPUT_DIR = os.path.dirname(OUTPUT_PATH)
os.makedirs(OUTPUT_ROOT, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)
OUTPUT_GTA_FILES = os.path.join(OUTPUT_ROOT, "output_gta")
os.makedirs(OUTPUT_GTA_FILES, exist_ok=True)
LOD_LIMIT = get_arg("LOD_LIMIT", 200.0, float)
VERTEX_LIMIT = get_arg("VERTEX_LIMIT", 32767, int)
# 📁 Caminhos de entrada e saída definidos via CMD ou padrão
#input_folder = OUTPUT_DIR
output_folder = os.path.join(OUTPUT_DIR, "splits_output")

os.makedirs(output_folder, exist_ok=True)
print(f"📦 [ARGS] MAP_NAME={MAP_NAME}")
print(f"📦 [ARGS] input_folder={OUTPUT_DIR}")
print(f"📦 [ARGS] output_folder={output_folder}")

# define caminho absoluto para texturas invisíveis, coloridas etc
output_texture_path = os.path.join(OUTPUT_DIR, "transparent_material.png")
texture_dir = os.path.join(OUTPUT_DIR, "textures")
os.makedirs(texture_dir, exist_ok=True)

print(f"📦 [ARGS] OUTPUT_PATH={OUTPUT_PATH}, LOD_LIMIT={LOD_LIMIT}, VERTEX_LIMIT={VERTEX_LIMIT}")

SEED                   = get_arg("seed", 1, int)
NUM_BLOCKS             = get_arg("blocks", 50, int)
STEP_LEN               = get_arg("step", 2.0, float)       # passo ao longo do traçado (m)
BASE_ROAD_WIDTH        = get_arg("road_w", 56.0, float)     # largura base (m)
SHOULDER_WIDTH_BASE    = get_arg("shoulder_w", 0.6, float) # acostamento base (m)
ROAD_THICKNESS         = get_arg("road_t", 1.40, float)    # espessura (m)

ROAD_MAT_COLOR      = (
    get_arg("road_r", 0.5, float),
    get_arg("road_g", 0.4, float),
    get_arg("road_b", 0.1, float),
    1.0,
)

# Barreiras (podem desligar com barriers=0)
BARRIERS               = get_arg("barriers", 1, int) == 1
BARRIER_HEIGHT         = get_arg("barrier_h", 1.6, float)
BARRIER_THICKNESS      = get_arg("barrier_t", 0.40, float)
BARRIER_OFFSET         = get_arg("barrier_off", 0.0, float)  # afastamento extra do bordo

BARRIER_MAT_COLOR      = (
    get_arg("barrier_r", 0.1, float),
    get_arg("barrier_g", 0.1, float),
    get_arg("barrier_b", 0.1, float),
    1.0,
)

# túnel invisível entre barreiras
TUNNEL_ENABLE      = get_arg("tunnel", 0, int) == 1       # ativa ou não
TUNNEL_HEIGHT      = get_arg("tunnel_h", 10.0, float)      # altura do túnel
TUNNEL_THICKNESS   = get_arg("tunnel_t", 0.40, float)     # espessura das paredes
TUNNEL_HAS_ROOF    = get_arg("tunnel_roof", 1, int) == 1  # gera teto
TUNNEL_ROOF_THICK  = get_arg("roof_t", 0.40, float)       # espessura do teto
TUNNEL_VISIBLE     = get_arg("tunnel_visible", 0, int) == 1  # se 1, gera material visível (pra debug)


# Dinâmica
TARGET_SPEED           = get_arg("v_ms", 45.0, float)  # velocidade alvo (m/s) ~ 162 km/h
BANK_MAX_DEG           = get_arg("bank_max", 10.0, float)
BANK_SMOOTH            = get_arg("bank_smooth", 0.25, float)  # 0..1 filtro exp
WIDTH_CURV_FACT        = get_arg("w_curv", 0.10, float)       # intensidade da variação de largura (0..~0.5)
PITCH_SMOOTH           = get_arg("pitch_smooth", 0.06, float) # suavização de pitch (0..1)

# Pós
MERGE_DIST             = get_arg("merge", 0.0001, float)
AUTO_SMOOTH_ANGLE_DEG  = get_arg("smooth_angle", 60.0, float)

# Piso lateral (área para prédios)
BUILD_PAD_ENABLE   = get_arg("pads", 1, int) == 1
BUILD_PAD_WIDTH    = get_arg("pad_w", 50.0, float)   # largura lateral (metros)
BUILD_PAD_HEIGHT   = get_arg("pad_h", 0.2, float)   # espessura do piso
BUILD_PAD_OFFSET   = get_arg("pad_off", 0.0, float) # distância extra após barreira

BUILD_PAD_MAT_COLOR      = (
    get_arg("buildpad_r", 0.1, float),
    get_arg("buildpad_g", 0.6, float),
    get_arg("buildpad_b", 0.6, float),
    1.0,
)

# prédios (blocos simples)
BUILDINGS_ENABLE      = get_arg("buildings", 1, int) == 1
BUILD_SIDE_L          = get_arg("build_L", 1, int) == 1  # gerar lado esquerdo
BUILD_SIDE_R          = get_arg("build_R", 1, int) == 1  # gerar lado direito
BUILD_DENSITY_M       = get_arg("build_step", 10.0, float)  # distância entre tentativas (m)
BUILD_PROB            = get_arg("build_prob", 0.85, float)  # chance de colocar prédio em cada tentativa
BUILD_MAT_COLOR      = (
    get_arg("build_r", 0.0, float),
    get_arg("build_g", 0.1, float),
    get_arg("build_b", 0.6, float),
    1.0,
)

# múltiplas fileiras de prédios
BUILD_ROWS           = get_arg("build_rows", 2, int)     # quantas fileiras por lado
ROW_SPACING          = get_arg("row_spacing", 20.0, float) # distância entre fileiras (m)
ROW_HEIGHT_VARIATION = get_arg("row_h_var", 0.4, float)  # variação de altura por fileira (fator 0..1)


# tamanhos (metros)
BUILD_W_MIN           = get_arg("b_w_min", 4.0, float)   # largura (eixo right)
BUILD_W_MAX           = get_arg("b_w_max", 12.0, float)
BUILD_D_MIN           = get_arg("b_d_min", 5.0, float)   # profundidade (eixo forward)
BUILD_D_MAX           = get_arg("b_d_max", 18.0, float)
BUILD_H_MIN           = get_arg("b_h_min", 6.0, float)   # altura (eixo up)
BUILD_H_MAX           = get_arg("b_h_max", 58.0, float)

# recuos e ajustes
BUILD_SETBACK         = get_arg("b_setback", 10.0, float)   # recuo a partir da borda EXTERNA do pad
BUILD_JITTER_R        = get_arg("b_jit_r", 0.8, float)     # aleatório lateral (m)
BUILD_JITTER_F        = get_arg("b_jit_f", 0.8, float)     # aleatório ao longo (m)

# orientação dos prédios
BUILD_ALIGN_WORLD = get_arg("build_align_world", 1, int) == 1  # 1 = reto (up global), 0 = segue inclinação local

# =====================================================
#  O B S T Á C U L O S   (PILARES / BARREIRAS / POSTES)
# =====================================================

# =====================================================
#  O B S T Á C U L O S   (PILARES / BARREIRAS / POSTES)
# =====================================================

OBSTACLES_ENABLE        = get_arg("obstacles", 1, int) == 1

# densidade e posicionamento
OBSTACLE_STEP_BASE      = get_arg("obs_step", 20.0, float)
OBSTACLE_STEP_CURVE     = get_arg("obs_step_curve", 12.0, float)
OBSTACLE_PROB           = get_arg("obs_prob", 0.7, float)

# dimensões
OBSTACLE_W_MIN          = get_arg("obs_w_min", 0.6, float)
OBSTACLE_W_MAX          = get_arg("obs_w_max", 2.0, float)
OBSTACLE_D_MIN          = get_arg("obs_d_min", 0.6, float)
OBSTACLE_D_MAX          = get_arg("obs_d_max", 2.5, float)
OBSTACLE_H_MIN          = get_arg("obs_h_min", 3.0, float)
OBSTACLE_H_MAX          = get_arg("obs_h_max", 10.0, float)

# variações e rotação
OBSTACLE_ROT_VARIATION  = get_arg("obs_rot_var", 10.0, float)
OBSTACLE_TILT_VARIATION = get_arg("obs_tilt_var", 4.0, float)
OBSTACLE_UP_OFFSET      = get_arg("obs_up_off", 0.0, float)
OBSTACLE_ALIGN_WORLD    = get_arg("obs_align_world", 1, int) == 1

# modos de posição lateral
# 1=centro, 2=alternado, 3=duplo, 4=aleatório
OBSTACLE_MODE           = get_arg("obs_mode", 2, int)
OBSTACLE_OFFSET_SIDE    = get_arg("obs_side_off", 4.0, float)
OBSTACLE_REVERSE        = get_arg("obs_reverse", 0, int) == 1

# agrupamento
OBSTACLE_GROUP_SIZE     = get_arg("obs_group_size", 1, int)
OBSTACLE_GROUP_SPACING  = get_arg("obs_group_spacing", 2.5, float)

# densidade adaptativa
OBSTACLE_CURVE_ONLY     = get_arg("obs_curve_only", 0, int) == 1
OBSTACLE_STEP_MULT_CURV = get_arg("obs_step_mult_curv", 0.6, float)  # curva = step_base * mult
OBSTACLE_BANK_THRESHOLD = get_arg("obs_bank_thr", 2.5, float)  # threshold pra detectar curva

# restrições e zonas
OBSTACLE_SKIP_TUNNEL    = get_arg("obs_skip_tunnel", 1, int) == 1
OBSTACLE_TUNNEL_MODE    = get_arg("obs_tunnel_mode", 0, int) == 1  # gera dentro do túnel (pendurado ou lateral)
OBSTACLE_TUNNEL_HANG    = get_arg("obs_tunnel_hang", 0, int) == 1  # se 1, pendura no teto

# formatos
# 1=pilar, 2=parede, 3=arco, 4=viga cruzada, 5=caixa sólida
OBSTACLE_TEMPLATE_MODE  = get_arg("obs_template", 2, int)

# deslocamento lateral aleatório dos obstáculos
OBSTACLE_SIDE_JITTER = get_arg("obs_side_jit", 14.0, float)  # variação lateral máxima (m)
OBSTACLE_JITTER_MODE = get_arg("obs_jit_mode", 2, int)      # 1=normal (bidirecional), 2=só para fora, 3=só para dentro


# aparência e debug
OBSTACLE_MAT_COLOR      = (
    get_arg("obs_r", 1.0, float),
    get_arg("obs_g", 0.35, float),
    get_arg("obs_b", 0.1, float),
    1.0,
)

# =====================================================
#  Q U A D R A S   I N I C I A I S  /  F I N A I S
# =====================================================

BLOCK_AREAS_ENABLE     = get_arg("block_areas", 1, int) == 1
BLOCK_START_ENABLE     = get_arg("block_start", 1, int) == 1
BLOCK_END_ENABLE       = get_arg("block_end", 1, int) == 1

# dimensões da quadra
BLOCK_LENGTH           = get_arg("block_len", 80.0, float)    # comprimento (m)
BLOCK_WIDTH            = get_arg("block_wid", 120.0, float)   # largura (m)
BLOCK_BUILD_HEIGHT     = get_arg("block_bh", 40.0, float)     # altura média dos prédios
BLOCK_BUILD_SPACING    = get_arg("block_spacing", 20.0, float)# espaçamento entre prédios
BLOCK_BUILD_DENSITY    = get_arg("block_density", 0.9, float) # chance de cada prédio aparecer

# barreiras invisíveis
BLOCK_BARRIERS         = get_arg("block_barriers", 1, int) == 1
BLOCK_BARRIER_HEIGHT   = get_arg("block_barrier_h", 10.0, float)
BLOCK_BARRIER_THICK    = get_arg("block_barrier_t", 0.5, float)
BLOCK_BARRIER_VISIBLE  = get_arg("block_barrier_visible", 0, int) == 1

# piso da quadra
BLOCK_FLOOR_HEIGHT     = get_arg("block_floor_h", 1.0, float)   # espessura do piso da quadra
BLOCK_FLOOR_VISIBLE    = get_arg("block_floor_vis", 1, int) == 1
BLOCK_FLOOR_MAT_COLOR  = (
    get_arg("block_floor_r", 0.05, float),
    get_arg("block_floor_g", 0.05, float),
    get_arg("block_floor_b", 0.05, float),
    1.0,
)

# barreira início/fim com configs independentes
BLOCK_START_BARRIER_VISIBLE = get_arg("block_start_barrier_vis", 1, int) == 1
BLOCK_START_BARRIER_HEIGHT  = get_arg("block_start_barrier_h", 12.0, float)
BLOCK_START_BARRIER_THICK   = get_arg("block_start_barrier_t", 0.6, float)

BLOCK_END_BARRIER_VISIBLE   = get_arg("block_end_barrier_vis", 1, int) == 1
BLOCK_END_BARRIER_HEIGHT    = get_arg("block_end_barrier_h", 12.0, float)
BLOCK_END_BARRIER_THICK     = get_arg("block_end_barrier_t", 0.6, float)

BLOCK_BARRIER_OFFSET_START = get_arg("block_barrier_off_start", 0.0, float)  # distância da quadra até a pista (m)
BLOCK_BARRIER_OFFSET_END   = get_arg("block_barrier_off_end", 0.0, float)

# =====================================================
#  S P A W N   P O I N T S   I N I C I A I S
# =====================================================

SPAWN_ENABLE          = get_arg("spawn_enable", 1, int) == 1
SPAWN_ROWS            = get_arg("spawn_rows", 2, int)     # número de filas (em profundidade)
SPAWN_PER_ROW         = get_arg("spawn_per_row", 4, int)  # quantos jogadores/veículos por fila
SPAWN_SPACING_X       = get_arg("spawn_spacing_x", 5.0, float)  # distância lateral (entre veículos)
SPAWN_SPACING_Y       = get_arg("spawn_spacing_y", 7.0, float)  # distância entre filas
SPAWN_OFFSET_FORWARD  = get_arg("spawn_offset_fwd", 10.0, float) # distância do início da pista
SPAWN_OFFSET_UP       = get_arg("spawn_offset_up", 1.0, float)   # altura do empty acima da pista
SPAWN_EMPTY_SIZE      = get_arg("spawn_empty_size", 1.2, float)  # tamanho visual dos empties

# =====================================================
#  C H E C K P O I N T S   &   R E S P A W N S
# =====================================================

CHECKPOINTS_ENABLE       = get_arg("checkpoints_enable", 1, int) == 1
CHECKPOINT_COUNT          = get_arg("checkpoint_count", 5, int)   # número total de checkpoints
CHECKPOINT_SPACING        = get_arg("checkpoint_spacing", 200.0, float)  # distância entre checkpoints
CHECKPOINT_OFFSET_UP      = get_arg("checkpoint_up", 1.0, float)
CHECKPOINT_RESPAWN_ROWS   = get_arg("respawn_rows", 2, int)
CHECKPOINT_RESPAWN_COLS   = get_arg("respawn_cols", 3, int)
CHECKPOINT_RESPAWN_SPACING_X = get_arg("respawn_spacing_x", 5.0, float)
CHECKPOINT_RESPAWN_SPACING_Y = get_arg("respawn_spacing_y", 8.0, float)
CHECKPOINT_RESPAWN_OFFSET_FWD = get_arg("respawn_off_fwd", 8.0, float)
CHECKPOINT_EMPTY_SIZE     = get_arg("checkpoint_empty_size", 1.2, float)


random.seed(SEED)

def create_simple_mat(name, rgba):
    """
    Cria material simples compatível com o Blender 4.3.
    Se alpha < 1.0, torna o material transparente (invisível em Material Preview / Render)
    mas visível no modo Solid através da cor de viewport.
    """
    import bpy

    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = rgba
    bsdf.inputs["Roughness"].default_value = 1.0

    alpha = rgba[3] if len(rgba) > 3 else 1.0

    # Configuração de transparência (Blender 4.3)
    if alpha < 1.0:
        m.blend_method = 'BLEND'      # material transparente
        m.use_backface_culling = False
        bsdf.inputs["Alpha"].default_value = alpha

        # Visível no modo Solid
        m.use_preview_world = False
        m.diffuse_color = (rgba[0], rgba[1], rgba[2], 1.0)

        # Viewport visibility (modo sólido)
        m.show_transparent_back = True
        m.use_screen_refraction = False
        m.use_sss_translucency = False
        # Desabilitar sombras (API 4.3+)
        if hasattr(m, "use_shadow_cast"):
            m.use_shadow_cast = False
    else:
        m.blend_method = 'OPAQUE'
        m.diffuse_color = (rgba[0], rgba[1], rgba[2], 1.0)

    return m



MAT_BARRIER = create_simple_mat("mat_barrier", BARRIER_MAT_COLOR)
MAT_BUILDING = create_simple_mat("mat_building", BUILD_MAT_COLOR)
MAT_ROAD = create_simple_mat("mat_road", ROAD_MAT_COLOR)
MAT_BUILDPAD = create_simple_mat("mat_buildpad", BUILD_PAD_MAT_COLOR)
MAT_TUNNEL = create_simple_mat("mat_tunnel_debug", (1, 0, 0, 0.0))
MAT_BLOCK_BARRIER = create_simple_mat("mat_block_barrier", (0.8, 0.0, 0.0, 0.0))
MAT_BLOCK_FLOOR = create_simple_mat("mat_block_floor", BLOCK_FLOOR_MAT_COLOR)
MAT_OBSTACLE = create_simple_mat("mat_obstacle", OBSTACLE_MAT_COLOR)


import bmesh

def add_box_oriented(collection, center, right, forward, up, size_r, size_f, size_u, name="Building"):
    """
    Cria um paralelepípedo orientado com winding consistente em todos os eixos.
    As normais sempre apontam para fora, mesmo em sistemas canhotos.
    """
    mesh = bpy.data.meshes.new(name)
    obj  = bpy.data.objects.new(name, mesh)
    collection.objects.link(obj)

    bm = bmesh.new()
    hx, hy, hz = size_r * 0.5, size_f * 0.5, size_u * 0.5

    ex = right.normalized() * hx
    ey = forward.normalized() * hy
    ez = up.normalized() * hz

    # Detecta se sistema é canhoto
    det = right.cross(forward).dot(up)
    left_handed = det < 0

    corners = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            for sz in (-1, 1):
                v = center + ex*sx + ey*sy + ez*sz
                corners.append(bm.verts.new(v))
    bm.verts.ensure_lookup_table()

    def idx(sx, sy, sz):
        return (0 if sx==-1 else 4) + (0 if sy==-1 else 2) + (0 if sz==-1 else 1)

    def make_face(a,b,c,d, want_dir):
        vs = [corners[a], corners[b], corners[c], corners[d]]
        n = (vs[1].co - vs[0].co).cross(vs[2].co - vs[0].co)
        if n.dot(want_dir) < 0:
            vs = [vs[0], vs[3], vs[2], vs[1]]
        bm.faces.new(vs)

    # Faces com normais desejadas
    make_face(idx( 1,-1,-1), idx( 1,-1, 1), idx( 1, 1, 1), idx( 1, 1,-1),  right)   # +X
    make_face(idx(-1, 1,-1), idx(-1, 1, 1), idx(-1,-1, 1), idx(-1,-1,-1), -right)  # -X
    make_face(idx(-1, 1,-1), idx( 1, 1,-1), idx( 1, 1, 1), idx(-1, 1, 1),  forward) # +Y
    make_face(idx( 1,-1,-1), idx(-1,-1,-1), idx(-1,-1, 1), idx( 1,-1, 1), -forward) # -Y
    make_face(idx(-1,-1, 1), idx( 1,-1, 1), idx( 1, 1, 1), idx(-1, 1, 1),  up)      # +Z
    make_face(idx(-1, 1,-1), idx( 1, 1,-1), idx( 1,-1,-1), idx(-1,-1,-1), -up)      # -Z

    bm.normal_update()
    bm.to_mesh(mesh)
    bm.free()
    return obj


# =========================
# BLOCO PROCEDURAL
# =========================

def block_straight(L=40.0):
    steps = max(1, int(L/STEP_LEN))
    for i in range(steps):
        t = (i+1)/steps
        yield 0.0, 0.0, STEP_LEN  # yawΔ, pitchΔ, ds

def block_curve(angle_deg=30.0, radius=60.0, left=True, ease_type="sin"):
    """
    Gera passos de curva com easing suave.
    ease_type: "sin" (padrão) ou "cos" etc. Mantém yaw_step crescendo e decrescendo.
    """
    arc = math.radians(abs(angle_deg)) * max(radius, 1e-6)
    steps = max(1, int(arc / STEP_LEN))
    yaw_total = angle_deg
    for i in range(steps):
        u = (i + 0.5) / steps  # 0..1
        if ease_type == "sin":
            ease = math.sin(u * math.pi)    # sin: 0->1->0 (suave)
        else:
            # fallback: cos ease-in-out
            ease = 0.5 - 0.5 * math.cos(u * math.pi)
        # yaw_step em graus (soma aproximada será < yaw_total; mas forma é mais suave)
        yaw_step = (yaw_total / steps) * ease
        if not left:
            yaw_step = -yaw_step
        yield yaw_step, 0.0, STEP_LEN

def block_grade(L=40.0, dz=8.0):
    steps = max(1, int(L/STEP_LEN))
    pitch_total = math.degrees(math.atan2(dz, L))
    for i in range(steps):
        u = (i+0.5)/steps
        ease = 0.5 - 0.5*math.cos(u*math.pi)  # cos-ease-in-out
        dpitch = (pitch_total/steps) * ease
        yield 0.0, dpitch, STEP_LEN

def random_block():
    t = random.choices(["S","CL","CR","U","D"], weights=[4,2,2,1,1])[0]
    if t == "S":
        return list(block_straight(L=random.uniform(30,60)))
    if t == "CL":
        return list(block_curve(angle_deg=random.choice([15,25,35]), radius=random.uniform(50,90), left=True))
    if t == "CR":
        return list(block_curve(angle_deg=random.choice([15,25,35]), radius=random.uniform(50,90), left=False))
    if t == "U":
        return list(block_grade(L=random.uniform(35,55), dz=random.uniform(6,12)))
    return list(block_grade(L=random.uniform(35,55), dz=-random.uniform(6,12)))

def program_from_blocks(n):
    prog = []
    for _ in range(n):
        prog += random_block()
    return prog

# =========================
# FRAMES COM SUAVIZAÇÃO
# =========================

def frames_from_program(program):
    """
    Integra posição e orientação (yaw/pitch), calcula forward/right/up.
    Banking alvo ~ atan(v^2/(r*g)) com clamp e filtro exponencial.
    Largura varia com curvatura (agora usando radianos corretamente).
    Adiciona suavização vertical (Z_SMOOTH) e clamp de dpitch por passo.
    """
    g = 9.81
    pos = Vector((0, 0, 0))
    yaw = 0.0
    pitch = 0.0
    bank_curr = 0.0
    s_accum = 0.0

    up_axis = Vector((0, 0, 1))
    frames = []

    # parâmetros de segurança/suavização (ajuste conforme preferir)
    Z_SMOOTH = 0.6                     # 0..1 suaviza pos.z (maior = mais suave)
    MAX_DPITCH_DEG_PER_STEP = 1.8     # limita variação de pitch por passo (graus)
    # (sugestões de alteração de defaults)
    # PITCH_SMOOTH = 0.08  # considere reduzir no call de get_arg se quiser ainda mais suave

    for (dyaw, dpitch, ds) in program:
        # clamp dpitch por step (evita picos)
        if dpitch > MAX_DPITCH_DEG_PER_STEP:
            dpitch = MAX_DPITCH_DEG_PER_STEP
        elif dpitch < -MAX_DPITCH_DEG_PER_STEP:
            dpitch = -MAX_DPITCH_DEG_PER_STEP

        # target pitch depois do incremento local
        target_pitch = pitch + dpitch
        # suaviza pitch por LERP explícito
        pitch = (1.0 - PITCH_SMOOTH) * pitch + PITCH_SMOOTH * target_pitch

        # direção sem roll (usa yaw atual; atualizamos yaw no final)
        cy, sy = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
        cp, sp = math.cos(math.radians(pitch)), math.sin(math.radians(pitch))
        forward = Vector((cy * cp, sy * cp, sp)).normalized()
        right = forward.cross(up_axis).normalized()
        upv = right.cross(forward).normalized()

        # curvatura corrigida (usar radianos por metro)
        curvature = abs(math.radians(dyaw)) / max(ds, 1e-6)   # rad/m
        r = 1.0 / max(curvature, 1e-6)

        # banking alvo (mais realista por usar radianos)
        bank_target = math.degrees(math.atan(min(1.0, (TARGET_SPEED ** 2) / (max(r, 1.0) * g))))
        bank_target = max(-BANK_MAX_DEG, min(BANK_MAX_DEG, bank_target)) * (1 if dyaw >= 0 else -1)

        # suaviza banking
        bank_curr = (1.0 - BANK_SMOOTH) * bank_curr + BANK_SMOOTH * bank_target

        # aplica roll ao par (right, up)
        m_roll = Matrix.Rotation(math.radians(bank_curr), 4, forward)
        right = (m_roll @ right).normalized()
        upv = (m_roll @ upv).normalized()

        # ajusta largura por curvatura (menos sensível porque curvature está em rad/m)
        width_factor = 1.0 - WIDTH_CURV_FACT * min(1.0, curvature * STEP_LEN * 4.0)
        road_w = BASE_ROAD_WIDTH * max(0.7, width_factor)
        shoulder_w = SHOULDER_WIDTH_BASE * (0.8 + 0.4 * width_factor)

        # integrar posição (raw)
        raw_pos = pos + forward * ds
        s_accum += ds

        # suavizar somente a componente Z para reduzir lombadas
        new_z = (1.0 - Z_SMOOTH) * pos.z + Z_SMOOTH * raw_pos.z
        pos = Vector((raw_pos.x, raw_pos.y, new_z))

        frames.append({
            "s": s_accum,
            "pos": pos.copy(),
            "fwd": forward.copy(),
            "right": right.copy(),
            "up": upv.copy(),
            "bank_deg": bank_curr,
            "road_w": road_w,
            "shoulder_w": shoulder_w
        })

        # atualiza yaw para próximo passo
        yaw += dyaw

    return frames

# =========================
# CONSTRUÇÃO DE MALHAS
# =========================

def face_safe(bm, vs):
    try: bm.faces.new(vs)
    except: pass

# --- helper robusto de winding/normal ---
def face_with_normal(bm, vs, want_dir=None):
    """
    Cria quad com winding consistente. Se want_dir for dado,
    calcula normal (v0,v1,v2) e inverte a ordem se necessário.
    """
    try:
        if want_dir is not None and len(vs) >= 3:
            n = (vs[1].co - vs[0].co).cross(vs[2].co - vs[0].co)
            # se a normal estiver oposta ao que queremos, invertimos o quad
            if n.dot(want_dir) < 0:
                vs = [vs[0], vs[3], vs[2], vs[1]]
        bm.faces.new(vs)
    except:
        pass


def build_block_area(center, forward, right, up, collection, name="BlockArea"):
    """
    Gera uma quadra com um piso sólido e prédios nas bordas.
    """
    half_w = BLOCK_WIDTH * 0.5
    half_l = BLOCK_LENGTH * 0.5

    # piso da quadra
    floor_center = center - up * (BLOCK_FLOOR_HEIGHT / 2)
    floor = add_box_oriented(
        collection, floor_center, right, forward, up,
        BLOCK_WIDTH, BLOCK_LENGTH, BLOCK_FLOOR_HEIGHT, name + "_Floor"
    )
    try:
        floor.data.materials.append(MAT_BLOCK_FLOOR)
    except:
        pass
    floor.hide_viewport = not BLOCK_FLOOR_VISIBLE
    floor.hide_render = not BLOCK_FLOOR_VISIBLE

    # grade de prédios
    nx = int(BLOCK_WIDTH / BLOCK_BUILD_SPACING)
    nz = int(BLOCK_LENGTH / BLOCK_BUILD_SPACING)

    for ix in range(-nx//2, nx//2 + 1):
        for iz in range(-nz//2, nz//2 + 1):
            if random.random() > BLOCK_BUILD_DENSITY:
                continue

            offset_r = right * (ix * BLOCK_BUILD_SPACING)
            offset_f = forward * (iz * BLOCK_BUILD_SPACING)
            pos = center + offset_r + offset_f

            # só gera prédios nas bordas
            if abs(ix) < nx//2 - 1 and abs(iz) < nz//2 - 1:
                continue

            h = random.uniform(BLOCK_BUILD_HEIGHT * 0.6, BLOCK_BUILD_HEIGHT * 1.2)
            w = random.uniform(6.0, 12.0)
            d = random.uniform(6.0, 12.0)
            pos += up * (h/2)

            obj = add_box_oriented(collection, pos, right, forward, up, w, d, h, f"{name}_B{ix}_{iz}")
            try:
                obj.data.materials.append(MAT_BUILDING)
            except:
                pass

    return floor

def build_block_barrier(center, forward, right, up, collection, is_start=True, name="Barrier_Custom"):
    """
    Cria barreiras de início/fim com configurações específicas.
    """
    forward = forward.normalized()
    right = right.normalized()
    up = up.normalized()

    if is_start:
        height = BLOCK_START_BARRIER_HEIGHT
        thick = BLOCK_START_BARRIER_THICK
        visible = BLOCK_START_BARRIER_VISIBLE
        offset = BLOCK_BARRIER_OFFSET_START
    else:
        height = BLOCK_END_BARRIER_HEIGHT
        thick = BLOCK_END_BARRIER_THICK
        visible = BLOCK_END_BARRIER_VISIBLE
        offset = BLOCK_BARRIER_OFFSET_END

    # move a barreira para dentro, na direção da pista
    center = center + forward * offset

    mesh = bpy.data.meshes.new(name)
    obj = bpy.data.objects.new(name, mesh)
    collection.objects.link(obj)
    bm = bmesh.new()

    # usa largura da estrada, não da quadra
    half_w = BASE_ROAD_WIDTH * 0.5
    # posições
    pBL = center - right * half_w
    pBR = center + right * half_w
    pTL = pBL + up * height
    pTR = pBR + up * height
    pOBL = pBL - forward * thick
    pOBR = pBR - forward * thick
    pOTL = pTL - forward * thick
    pOTR = pTR - forward * thick

    # vértices
    vBL = bm.verts.new(pBL)
    vBR = bm.verts.new(pBR)
    vTL = bm.verts.new(pTL)
    vTR = bm.verts.new(pTR)
    vOBL = bm.verts.new(pOBL)
    vOBR = bm.verts.new(pOBR)
    vOTL = bm.verts.new(pOTL)
    vOTR = bm.verts.new(pOTR)

    bm.verts.ensure_lookup_table()

    def make_face(vs, want_dir):
        try:
            n = (vs[1].co - vs[0].co).cross(vs[2].co - vs[0].co)
            if n.dot(want_dir) < 0:
                vs = [vs[0], vs[3], vs[2], vs[1]]
            bm.faces.new(vs)
        except:
            pass

    # faces com normais corretas
    make_face([vBL, vBR, vTR, vTL],  up)       # frente (voltada para cima da estrada)
    make_face([vOBL, vOTL, vOTR, vOBR], -forward)  # traseira
    make_face([vBL, vTL, vOTL, vOBL], -right)  # lado esquerdo
    make_face([vBR, vOBR, vOTR, vTR],  right)  # lado direito
    make_face([vTL, vTR, vOTR, vOTL],  up)     # topo
    make_face([vBL, vOBL, vOBR, vBR], -up)     # base


    bm.to_mesh(mesh)
    bm.free()

    if visible:
        obj.data.materials.append(MAT_BLOCK_BARRIER)
    obj.hide_viewport = not visible
    obj.hide_render = not visible

    return obj


def build_invisible_barrier(center, forward, right, up, collection, name="InvisibleBarrier"):
    """
    Cria uma parede/barreira invisível transversal à pista (um “caixote” fino).
    Usa forward/right/up como eixos locais.
    """
    # garanta vetores normalizados
    forward = forward.normalized()
    right   = right.normalized()
    up      = up.normalized()

    half_w = BLOCK_WIDTH * 0.5
    thick  = BLOCK_BARRIER_THICK

    # ---- POSIÇÕES (Vector) ----
    pBL = center - right * half_w
    pBR = center + right * half_w
    pTL = pBL + up * BLOCK_BARRIER_HEIGHT
    pTR = pBR + up * BLOCK_BARRIER_HEIGHT

    # desloca para trás/à frente usando apenas Vectors (nada de BMVert aqui)
    pOUT_BL = pBL - forward * thick
    pOUT_BR = pBR - forward * thick
    pOUT_TL = pTL - forward * thick
    pOUT_TR = pTR - forward * thick

    # ---- CRIAÇÃO DO BMESH ----
    mesh = bpy.data.meshes.new(name)
    obj  = bpy.data.objects.new(name, mesh)
    collection.objects.link(obj)
    bm = bmesh.new()

    # cria vértices a partir das posições calculadas
    vBL = bm.verts.new(pBL)
    vBR = bm.verts.new(pBR)
    vTL = bm.verts.new(pTL)
    vTR = bm.verts.new(pTR)

    vOBL = bm.verts.new(pOUT_BL)
    vOBR = bm.verts.new(pOUT_BR)
    vOTL = bm.verts.new(pOUT_TL)
    vOTR = bm.verts.new(pOUT_TR)

    bm.verts.ensure_lookup_table()

    def face_safe(vs):
        try:
            bm.faces.new(vs)
        except:
            pass

    # faces (ordem consistente para normais)
    # frente (voltada para +forward)
    face_safe([vBL, vBR, vTR, vTL])
    # trás (voltada para -forward)
    face_safe([vOBL, vOTL, vOTR, vOBR])
    # lateral esquerda
    face_safe([vBL, vTL, vOTL, vOBL])
    # lateral direita
    face_safe([vBR, vOBR, vOTR, vTR])
    # topo
    face_safe([vTL, vTR, vOTR, vOTL])
    # base (opcional; deixa fechado)
    face_safe([vBL, vOBL, vOBR, vBR])

    bm.normal_update()
    bm.to_mesh(mesh)
    bm.free()

    if BLOCK_BARRIER_VISIBLE:
        try:
            obj.data.materials.append(MAT_BLOCK_BARRIER)
        except:
            pass
    obj.hide_viewport = not BLOCK_BARRIER_VISIBLE
    obj.hide_render   = not BLOCK_BARRIER_VISIBLE

    return obj


def build_road(frames, collection):
    mesh = bpy.data.meshes.new("RoadMesh")
    obj  = bpy.data.objects.new("RoadMesh", mesh)
    collection.objects.link(obj)
    bm = bmesh.new()

    TL, TR, BL, BR = [], [], [], []
    Rs, Us, Fs = [], [], []  # guarda vetores por frame

    half_t = ROAD_THICKNESS * 0.5

    for f in frames:
        pos   = f["pos"]
        right = f["right"].normalized()
        up    = f["up"].normalized()
        fwd   = f["fwd"].normalized()

        # bordas esquerda/direita
        left  = -right
        wL = (f["road_w"]*0.5 + f["shoulder_w"])
        wR = (f["road_w"]*0.5 + f["shoulder_w"])

        TL.append(bm.verts.new(pos + left*wL  + up*half_t))
        TR.append(bm.verts.new(pos + right*wR + up*half_t))
        BL.append(bm.verts.new(pos + left*wL  - up*half_t))
        BR.append(bm.verts.new(pos + right*wR - up*half_t))

        Rs.append(right); Us.append(up); Fs.append(fwd)

    # faces entre segmentos (usa want_dir por face)
    for i in range(len(frames)-1):
        up_i    = Us[i]
        right_i = Rs[i]
        fwd_i   = Fs[i]

        # topo: +up
        face_with_normal(bm, [TL[i], TR[i], TR[i+1], TL[i+1]], want_dir= up_i)
        # base: -up
        face_with_normal(bm, [BL[i], BR[i], BR[i+1], BL[i+1]], want_dir=-up_i)

        # lateral esquerda (externa): -right
        face_with_normal(bm, [TL[i], TL[i+1], BL[i+1], BL[i]],  want_dir=-right_i)
        # lateral direita (externa): +right
        face_with_normal(bm, [BR[i], BR[i+1], TR[i+1], TR[i]],  want_dir= right_i)

    # caps (se existirem)
    if TL:
        # cap inicial: -fwd
        face_with_normal(bm, [BL[0], BR[0], TR[0], TL[0]], want_dir= -Fs[0])
        # cap final: +fwd
        n = len(TL)-1
        face_with_normal(bm, [TL[n], TR[n], BR[n], BL[n]], want_dir=  Fs[n])

    bm.normal_update()
    bm.to_mesh(mesh)
    bm.free()
    try:
        obj.data.materials.append(MAT_ROAD)
    except:
        pass
    return obj



def build_barrier(frames, collection, side=1):
    mesh = bpy.data.meshes.new(f"Barrier_{'R' if side==1 else 'L'}")
    obj  = bpy.data.objects.new(mesh.name, mesh)
    collection.objects.link(obj)
    bm = bmesh.new()

    quads = []
    for f in frames:
        # vetores normalizados do frame
        pos   = f["pos"]
        right = f["right"].normalized()
        up    = f["up"].normalized()
        fwd   = f["fwd"].normalized()

        edge_off = (f["road_w"]*0.5 + f["shoulder_w"] + BARRIER_OFFSET)

        base_c = pos + right*(edge_off*side) + up*(ROAD_THICKNESS/2)
        tdir   = right*(BARRIER_THICKNESS*side)

        # seção (BL, BR, TR, TL)
        BL = bm.verts.new(base_c)
        BR = bm.verts.new(base_c + tdir)
        TL = bm.verts.new(base_c + up*BARRIER_HEIGHT)
        TR = bm.verts.new(base_c + tdir + up*BARRIER_HEIGHT)

        # guardamos também os vetores desse frame p/ “want_dir”
        quads.append((BL, BR, TR, TL, right, up, fwd))

    for i in range(len(quads)-1):
        a0,a1,a2,a3, ar, au, af = quads[i]
        b0,b1,b2,b3, br, bu, bf = quads[i+1]

        # base (queremos normal para baixo: -up)
        face_with_normal(bm, [a0, a1, b1, b0], want_dir = -au)
        # topo (queremos normal para cima: +up)
        face_with_normal(bm, [a3, a2, b2, b3], want_dir =  au)

        # face externa (lado de fora da rua) → +right * side
        face_with_normal(bm, [a1, a2, b2, b1], want_dir =  ar * side)
        # face interna (voltada para a pista)  → -right * side
        face_with_normal(bm, [a0, b0, b3, a3], want_dir = -ar * side)

    # tampas (início/fim), se existir pelo menos uma seção
    if quads:
        a0,a1,a2,a3, ar, au, af = quads[0]
        # tampa inicial (voltada para trás): -forward
        face_with_normal(bm, [a3, a2, a1, a0], want_dir = -af)

        b0,b1,b2,b3, br, bu, bf = quads[-1]
        # tampa final (voltada para frente): +forward
        face_with_normal(bm, [b0, b1, b2, b3], want_dir =  bf)

    bm.normal_update()
    bm.to_mesh(mesh)
    bm.free()

    try:
        obj.data.materials.append(MAT_BARRIER)
    except:
        pass
    return obj



def build_buildpad(frames, collection, side=1):
    mesh = bpy.data.meshes.new(f"BuildPad_{'R' if side==1 else 'L'}")
    obj  = bpy.data.objects.new(mesh.name, mesh)
    collection.objects.link(obj)
    bm = bmesh.new()

    quads = []
    for f in frames:
        pos, right, up = f["pos"], f["right"], f["up"]
        edge_off = (f["road_w"]*0.5 + f["shoulder_w"]
                    + BARRIER_OFFSET + BARRIER_THICKNESS + BUILD_PAD_OFFSET)
        base_c = pos + right*(edge_off*side) + up*(ROAD_THICKNESS/2)
        pad_dir = right*(BUILD_PAD_WIDTH*side)

        BL = bm.verts.new(base_c)
        BR = bm.verts.new(base_c + pad_dir)
        TL = bm.verts.new(base_c + up*BUILD_PAD_HEIGHT)
        TR = bm.verts.new(base_c + pad_dir + up*BUILD_PAD_HEIGHT)
        quads.append((BL,BR,TR,TL))

    for i in range(len(quads)-1):
        a0,a1,a2,a3 = quads[i]
        b0,b1,b2,b3 = quads[i+1]

        if side == 1:
            # lado direito (sentido normal)
            face_safe(bm, [a0,a1,b1,b0])  # base
            face_safe(bm, [a3,a2,b2,b3])  # topo
            face_safe(bm, [a1,a2,b2,b1])  # externa
            face_safe(bm, [a0,b0,b3,a3])  # interna
        else:
            # lado esquerdo (espelhar winding)
            face_safe(bm, [a0,b0,b1,a1])  # base
            face_safe(bm, [a3,b3,b2,a2])  # topo
            face_safe(bm, [a1,b1,b2,a2])  # externa
            face_safe(bm, [a0,a3,b3,b0])  # interna


    if quads:
        a0,a1,a2,a3 = quads[0]
        if side == 1:
            bm.faces.new([a3,a2,a1,a0])
        else:
            bm.faces.new([a0,a1,a2,a3])

        b0,b1,b2,b3 = quads[-1]
        if side == 1:
            bm.faces.new([b0,b1,b2,b3])
        else:
            bm.faces.new([b3,b2,b1,b0])


    bm.normal_update()
    bm.to_mesh(mesh)
    bm.free()
    try:
        obj.data.materials.append(MAT_BUILDPAD)
    except:
        pass
    return obj

def build_tunnel(frames, collection):
    """
    Gera um túnel quadrado/retangular conectando as barreiras,
    garantindo winding consistente (sem depender de recalc normals).
    """
    mesh = bpy.data.meshes.new("Tunnel")
    obj  = bpy.data.objects.new("Tunnel", mesh)
    collection.objects.link(obj)
    bm = bmesh.new()

    quads = []
    for f in frames:
        pos, right, up = f["pos"], f["right"].normalized(), f["up"].normalized()
        # distância lateral até cada barreira
        edge_offset = (f["road_w"]*0.5 + f["shoulder_w"] + BARRIER_OFFSET)

        # posições base (centro das paredes esquerda e direita)
        left_base  = pos - right * (edge_offset + BARRIER_THICKNESS/2)
        right_base = pos + right * (edge_offset + BARRIER_THICKNESS/2)

        # define topo e base
        floor_z = ROAD_THICKNESS/2
        top_z   = floor_z + TUNNEL_HEIGHT

        # espessuras
        t_thick = TUNNEL_THICKNESS
        r_thick = TUNNEL_ROOF_THICK  # (usado no teto externo)

        # vértices principais das duas paredes
        # lado esquerdo (interno = sem deslocamento em -right; externo = -right * t_thick)
        L_BI = bm.verts.new(left_base + up*floor_z)                 # bottom inner
        L_TO = bm.verts.new(left_base + up*top_z)                    # top inner
        L_BE = bm.verts.new(left_base + up*floor_z - right*t_thick)  # bottom external
        L_TE = bm.verts.new(left_base + up*top_z   - right*t_thick)  # top external

        # lado direito (interno = sem deslocamento; externo = +right * t_thick)
        R_BI = bm.verts.new(right_base + up*floor_z)
        R_TO = bm.verts.new(right_base + up*top_z)
        R_BE = bm.verts.new(right_base + up*floor_z + right*t_thick)
        R_TE = bm.verts.new(right_base + up*top_z   + right*t_thick)

        quads.append((L_BI,L_TO,L_TE,L_BE,  R_BI,R_TO,R_TE,R_BE,  right, up))

    # faces entre segmentos
    for i in range(len(quads)-1):
        a = quads[i]
        b = quads[i+1]
        # desempacota + vetores alvo locais (do segmento 'a')
        L_BI,L_TO,L_TE,L_BE,  R_BI,R_TO,R_TE,R_BE,  right, up = a
        L_BI2,L_TO2,L_TE2,L_BE2,  R_BI2,R_TO2,R_TE2,R_BE2,  right2, up2 = b

        # --- paredes internas (normais apontando para dentro do túnel) ---
        # esquerda (queremos +right)
        face_with_normal(bm, [L_BI, L_TO, L_TO2, L_BI2], want_dir= right)
        # direita (queremos -right)
        face_with_normal(bm, [R_BI, R_TO, R_TO2, R_BI2], want_dir=-right)

        # --- paredes externas (normais apontando para fora) ---
        # esquerda externa (queremos -right)
        face_with_normal(bm, [L_BE, L_TE, L_TE2, L_BE2], want_dir=-right)
        # direita externa (queremos +right)
        face_with_normal(bm, [R_BE, R_TE, R_TE2, R_BE2], want_dir= right)

        # --- teto (se ativado) ---
        if TUNNEL_HAS_ROOF:
            # interno (queremos normal para baixo = -up)
            face_with_normal(bm, [L_TO, R_TO, R_TO2, L_TO2], want_dir=-up)
            # externo (espessura do teto; queremos normal para cima = +up)
            face_with_normal(bm, [L_TE, R_TE, R_TE2, L_TE2], want_dir= up)

        # (opcional) pode fechar o piso se quiser um “caixote” completo:
        # interno do piso (normal para cima = +up):
        # face_with_normal(bm, [L_BI, R_BI, R_BI2, L_BI2], want_dir= up)
        # externo do piso (normal para baixo = -up):
        # face_with_normal(bm, [L_BE, R_BE, R_BE2, L_BE2], want_dir=-up)

    bm.normal_update()
    bm.to_mesh(mesh)
    bm.free()

    if TUNNEL_VISIBLE:
        try:
            obj.data.materials.append(MAT_TUNNEL)
        except:
            pass
    obj.hide_viewport = not TUNNEL_VISIBLE
    obj.hide_render   = not TUNNEL_VISIBLE

    return obj



# =========================
# UTILIDADES (pós)
# =========================

def postprocess(obj):
    # shade smooth
    try:
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        bpy.ops.object.shade_smooth()
    except:
        pass

    mesh = obj.data
    if hasattr(mesh, "use_auto_smooth"):
        mesh.use_auto_smooth = True
        mesh.auto_smooth_angle = math.radians(AUTO_SMOOTH_ANGLE_DEG)

    # merge by distance
    try:
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.remove_doubles(threshold=MERGE_DIST)
        bpy.ops.object.mode_set(mode='OBJECT')
    except:
        try:
            bpy.ops.object.mode_set(mode='OBJECT')
        except:
            pass
    obj.select_set(False)
    
def build_buildings_along_pads(frames, collection, side=1):
    """
    Gera prédios em múltiplas fileiras no lado 'side'.
    Cada fileira fica mais afastada da estrada.
    """
    s_next = BUILD_DENSITY_M
    i = 0
    while i < len(frames):
        f = frames[i]
        if f["s"] >= s_next:
            if random.random() <= BUILD_PROB:
                pos     = f["pos"]
                right   = f["right"]
                forward = f["fwd"]
                up      = f["up"]

                # se habilitado, força prédios verticais (up global)
                if BUILD_ALIGN_WORLD:
                    up = Vector((0, 0, 1))
                    # re-ortogonaliza right/forward em torno de up global
                    forward = Vector((forward.x, forward.y, 0)).normalized()
                    right = Vector((0,0,1)).cross(forward).normalized()  # up_global × forward



                # base do pad relativa ao centro da pista
                edge_to_pad_start = (
                    f["road_w"]*0.5 +
                    f["shoulder_w"] +
                    BARRIER_OFFSET + BARRIER_THICKNESS +
                    BUILD_PAD_OFFSET
                )

                pad_half = BUILD_PAD_WIDTH * 0.5

                for row in range(BUILD_ROWS):
                    # distância lateral até o início da fileira
                    row_offset = (
                        edge_to_pad_start +           # até o início do pad
                        BUILD_SETBACK +               # recuo antes do prédio
                        (row * ROW_SPACING)           # espaço adicional por fileira
                    )

                    center_base = (
                        pos
                        + right * (row_offset * side)
                        + up * (ROAD_THICKNESS/2 + BUILD_PAD_HEIGHT)
                    )

                    jitter_r = (random.random()*2-1) * BUILD_JITTER_R
                    jitter_f = (random.random()*2-1) * BUILD_JITTER_F
                    center = center_base + right*(jitter_r*side) + forward*jitter_f

                    w = random.uniform(BUILD_W_MIN, BUILD_W_MAX)
                    d = random.uniform(BUILD_D_MIN, BUILD_D_MAX)
                    h_mod = 1.0 + (random.uniform(-ROW_HEIGHT_VARIATION, ROW_HEIGHT_VARIATION) * (row+1))
                    h = random.uniform(BUILD_H_MIN, BUILD_H_MAX) * h_mod

                    # mantém sistema de coordenadas destro para evitar faces invertidas
                    right_fixed = right * side
                    forward_fixed = forward
                    if side == -1:
                        forward_fixed = -forward

                    obj = add_box_oriented(collection, center, right_fixed, forward_fixed, up, w, d, h, name=f"Building_r{row}")

                    try:
                        obj.data.materials.append(MAT_BUILDING)
                    except:
                        pass
            s_next += BUILD_DENSITY_M
        i += 1

def make_obstacle_form(collection, pos, right, forward, up, w, d, h, mode, name="Obstacle"):
    """
    Cria diferentes tipos de obstáculos:
      1=pilar (retângulo simples)
      2=parede transversal
      3=arco (duas colunas + viga superior)
      4=viga cruzada (X)
      5=caixa sólida
    """
    objs = []

    def box(center, w_, d_, h_, label):
        o = add_box_oriented(collection, center, right, forward, up, w_, d_, h_, label)
        objs.append(o)
        return o

    if mode == 1:
        box(pos, w, d, h, name)
    elif mode == 2:
        # parede transversal (longa na largura)
        box(pos, w * 3, d * 0.5, h, name + "_wall")
    elif mode == 3:
        # arco (duas colunas e uma viga)
        offset = right * (w * 1.2)
        col_h = h * 0.8
        col_w = w * 0.4
        col_d = d * 0.8
        top_h = h * 0.2
        box(pos - offset, col_w, col_d, col_h, name + "_L")
        box(pos + offset, col_w, col_d, col_h, name + "_R")
        box(pos + up * (col_h - top_h / 2), w * 3, col_d, top_h, name + "_beam")
    elif mode == 4:
        # viga cruzada (X)
        tilt = math.radians(45)
        for s in (-1, 1):
            m = Matrix.Rotation(tilt * s, 4, forward)
            r2 = (m @ right).normalized()
            box(pos, w, d, h, name + f"_x{s}")
    elif mode == 5:
        # caixa sólida (cheia, tipo container)
        box(pos, w * 1.5, d * 1.5, h, name + "_box")

    for o in objs:
        try:
            o.data.materials.append(MAT_OBSTACLE)
        except:
            pass
    return objs


def build_obstacles(frames, collection):
    """
    Gera obstáculos (pilares, paredes, arcos, etc.) ao longo da pista.
    Possui suporte a curvas, agrupamento e variação procedural.
    """
    s_next = OBSTACLE_STEP_BASE
    side_toggle = -1

    for i, f in enumerate(frames):
        s = f["s"]
        if s < s_next:
            continue

        curvature = abs(f.get("bank_deg", 0.0))
        is_curve = curvature > OBSTACLE_BANK_THRESHOLD

        if OBSTACLE_CURVE_ONLY and not is_curve:
            continue

        step_here = OBSTACLE_STEP_BASE
        if is_curve:
            step_here *= OBSTACLE_STEP_MULT_CURV
        s_next += step_here

        if random.random() > OBSTACLE_PROB:
            continue

        pos = f["pos"]
        right = f["right"]
        forward = f["fwd"]
        up = f["up"]

        if OBSTACLE_ALIGN_WORLD:
            up = Vector((0, 0, 1))
            forward = Vector((forward.x, forward.y, 0)).normalized()
            right = forward.cross(up).normalized()

        # modos de posicionamento
        sides_to_spawn = []
        if OBSTACLE_MODE == 1:
            sides_to_spawn = [0]
        elif OBSTACLE_MODE == 2:
            side_toggle *= -1
            sides_to_spawn = [side_toggle]
        elif OBSTACLE_MODE == 3:
            sides_to_spawn = [-1, 1]
        elif OBSTACLE_MODE == 4:
            sides_to_spawn = [random.choice([-1, 0, 1])]

        if OBSTACLE_REVERSE:
            sides_to_spawn = [-s for s in sides_to_spawn]

        # variação de rotação
        yaw_rot = math.radians(random.uniform(-OBSTACLE_ROT_VARIATION, OBSTACLE_ROT_VARIATION))
        tilt_rot = math.radians(random.uniform(-OBSTACLE_TILT_VARIATION, OBSTACLE_TILT_VARIATION))

        m_yaw = Matrix.Rotation(yaw_rot, 4, up)
        m_tilt = Matrix.Rotation(tilt_rot, 4, right)
        right_r = (m_yaw @ m_tilt @ right).normalized()
        forward_r = (m_yaw @ m_tilt @ forward).normalized()

        for side in sides_to_spawn:
            # deslocamento base + jitter lateral
            offset = right * (OBSTACLE_OFFSET_SIDE * side)

            # calcula jitter lateral aleatório
            jitter_val = random.uniform(-OBSTACLE_SIDE_JITTER, OBSTACLE_SIDE_JITTER)
            if OBSTACLE_JITTER_MODE == 2:  # só para fora
                jitter_val = abs(jitter_val)
            elif OBSTACLE_JITTER_MODE == 3:  # só para dentro
                jitter_val = -abs(jitter_val)

            # aplica jitter no mesmo sentido do lado
            offset += right * (jitter_val * side if side != 0 else jitter_val)

            base = pos + offset + up * (ROAD_THICKNESS/2 + OBSTACLE_UP_OFFSET)


            # múltiplos pilares por grupo
            for g in range(OBSTACLE_GROUP_SIZE):
                gpos = base + forward_r * (g * OBSTACLE_GROUP_SPACING)

                # dentro do túnel, se habilitado
                if OBSTACLE_TUNNEL_MODE:
                    if OBSTACLE_TUNNEL_HANG:
                        gpos += up * (TUNNEL_HEIGHT - OBSTACLE_H_MAX/2)
                    else:
                        gpos += up * (ROAD_THICKNESS/2)
                elif OBSTACLE_SKIP_TUNNEL and pos.z < 0:
                    continue

                w = random.uniform(OBSTACLE_W_MIN, OBSTACLE_W_MAX)
                d = random.uniform(OBSTACLE_D_MIN, OBSTACLE_D_MAX)
                h = random.uniform(OBSTACLE_H_MIN, OBSTACLE_H_MAX)

                make_obstacle_form(
                    collection, gpos, right_r, forward_r, up,
                    w, d, h, OBSTACLE_TEMPLATE_MODE, f"Obstacle_{i}_s{side}_g{g}"
                )

def build_spawn_points(start_frame, collection):
    """
    Gera uma formação de empties de spawn no início da pista.
    Agora usando rotação em Euler XYZ.
    """
    fwd, right, up = start_frame["fwd"], start_frame["right"], start_frame["up"]
    base_pos = start_frame["pos"] + fwd * SPAWN_OFFSET_FORWARD + up * SPAWN_OFFSET_UP

    total_width = (SPAWN_PER_ROW - 1) * SPAWN_SPACING_X
    half_width = total_width / 2.0

    for row in range(SPAWN_ROWS):
        for col in range(SPAWN_PER_ROW):
            offset_r = right * (col * SPAWN_SPACING_X - half_width)
            offset_f = fwd * (-row * SPAWN_SPACING_Y)
            pos = base_pos + offset_r + offset_f

            empty = bpy.data.objects.new(f"Spawn_{row}_{col}", None)
            empty.location = pos
            empty.empty_display_size = SPAWN_EMPTY_SIZE
            empty.empty_display_type = "ARROWS"
            empty.rotation_mode = "XYZ"

            quat = fwd.to_track_quat("Z", "Y")  # antes usado diretamente
            empty.rotation_euler = quat.to_euler("XYZ")  # converte para Euler

            collection.objects.link(empty)

            # adiciona propriedades customizadas
            empty["spawn_row"] = row
            empty["spawn_col"] = col
            empty["spawn_index"] = row * SPAWN_PER_ROW + col
            empty["spawn_name"] = f"spawn_{row}_{col}"

    print(f"[TrackGen] Gerados {SPAWN_ROWS * SPAWN_PER_ROW} spawn points.")


def build_checkpoints(frames, collection):
    """
    Gera empties de checkpoint com pontos de respawn próximos.
    Agora usando Euler XYZ em vez de Quaternions.
    """
    total_frames = len(frames)
    step = max(1, int(CHECKPOINT_SPACING / (frames[-1]["s"] / total_frames)))
    checkpoint_id = 0

    for i in range(0, total_frames, step):
        f = frames[i]
        pos = f["pos"]
        fwd = f["fwd"]
        right = f["right"]
        up = f["up"]

        # empty principal do checkpoint
        chk = bpy.data.objects.new(f"Checkpoint_{checkpoint_id}", None)
        chk.location = pos + up * CHECKPOINT_OFFSET_UP
        chk.empty_display_type = "CUBE"
        chk.empty_display_size = CHECKPOINT_EMPTY_SIZE * 1.5
        chk.rotation_mode = "XYZ"

        quat = fwd.to_track_quat("Z", "Y")
        chk.rotation_euler = quat.to_euler("XYZ")

        collection.objects.link(chk)
        chk["checkpoint_id"] = checkpoint_id

        # gera respawns ao redor
        base_pos = pos + fwd * CHECKPOINT_RESPAWN_OFFSET_FWD + up * CHECKPOINT_OFFSET_UP
        total_w = (CHECKPOINT_RESPAWN_COLS - 1) * CHECKPOINT_RESPAWN_SPACING_X
        half_w = total_w / 2.0

        for r in range(CHECKPOINT_RESPAWN_ROWS):
            for c in range(CHECKPOINT_RESPAWN_COLS):
                offset_r = right * (c * CHECKPOINT_RESPAWN_SPACING_X - half_w)
                offset_f = fwd * (-r * CHECKPOINT_RESPAWN_SPACING_Y)
                p = base_pos + offset_r + offset_f

                e = bpy.data.objects.new(f"Respawn_{checkpoint_id}_{r}_{c}", None)
                e.location = p
                e.empty_display_type = "ARROWS"
                e.empty_display_size = CHECKPOINT_EMPTY_SIZE
                e.rotation_mode = "XYZ"

                quat_r = fwd.to_track_quat("Z", "Y")
                e.rotation_euler = quat_r.to_euler("XYZ")

                collection.objects.link(e)

                # custom props
                e["checkpoint_id"] = checkpoint_id
                e["respawn_row"] = r
                e["respawn_col"] = c
                e["respawn_index"] = r * CHECKPOINT_RESPAWN_COLS + c
                e["is_respawn_point"] = True

        checkpoint_id += 1

    print(f"[TrackGen] Gerados {checkpoint_id} checkpoints com respawns.")


import math

def export_game_data(json_path=None):
    """
    Exporta dados úteis ao GTA/FiveM:
      - âncoras de malhas (splits)
      - spawn points iniciais
      - checkpoints e respawns
    Tudo em um único arquivo JSON para leitura simples no jogo.
    As rotações são exportadas em GRAUS (Euler XYZ).
    """
    if not json_path:
        json_path = os.path.join(OUTPUT_DIR, "track_data.json")

    data = {
        "meshes": [],
        "spawn_points": [],
        "checkpoints": [],
        "respawns": []
    }

    def rot_to_deg(euler):
        return [
            round(math.degrees(euler.x), 3),
            round(math.degrees(euler.y), 3),
            round(math.degrees(euler.z), 3)
        ]

    # 1️⃣ Anchors (malhas splittadas)
    for obj in bpy.data.objects:
        if obj.type == "MESH" and "_split_" in obj.name:
            loc = obj.location
            rot = obj.rotation_euler
            data["meshes"].append({
                "name": obj.name,
                "pos": [round(loc.x, 3), round(loc.y, 3), round(loc.z, 3)],
                "rot": rot_to_deg(rot)
            })

    # 2️⃣ Spawn Points
    for obj in bpy.data.objects:
        if obj.name.startswith("Spawn_"):
            loc = obj.location
            rot = obj.rotation_euler
            data["spawn_points"].append({
                "name": obj.name,
                "pos": [round(loc.x, 3), round(loc.y, 3), round(loc.z, 3)],
                "rot": rot_to_deg(rot),
                "row": int(obj.get("spawn_row", 0)),
                "col": int(obj.get("spawn_col", 0)),
                "index": int(obj.get("spawn_index", 0))
            })

    # 3️⃣ Checkpoints + Respawns
    for obj in bpy.data.objects:
        if obj.name.startswith("Checkpoint_"):
            loc = obj.location
            rot = obj.rotation_euler
            cid = int(obj.get("checkpoint_id", 0))

            checkpoint_entry = {
                "id": cid,
                "name": obj.name,
                "pos": [round(loc.x, 3), round(loc.y, 3), round(loc.z, 3)],
                "rot": rot_to_deg(rot),
                "respawns": []
            }

            # respawns correspondentes
            for e in bpy.data.objects:
                if e.name.startswith(f"Respawn_{cid}_"):
                    eloc = e.location
                    erot = e.rotation_euler
                    checkpoint_entry["respawns"].append({
                        "name": e.name,
                        "pos": [round(eloc.x, 3), round(eloc.y, 3), round(eloc.z, 3)],
                        "rot": rot_to_deg(erot),
                        "row": int(e.get("respawn_row", 0)),
                        "col": int(e.get("respawn_col", 0)),
                        "index": int(e.get("respawn_index", 0))
                    })

            data["checkpoints"].append(checkpoint_entry)
            data["respawns"] += checkpoint_entry["respawns"]

    # salva arquivo
    json_path = os.path.abspath(json_path)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    print(f"💾 Dados exportados para {json_path}")
    print(f"  {len(data['meshes'])} meshes, {len(data['spawn_points'])} spawns, "
          f"{len(data['checkpoints'])} checkpoints, {len(data['respawns'])} respawns.")

    return data


def recalc_normals_outside(obj):
    if obj.type != 'MESH':
        return
    me = obj.data
    # Garante cálculo atualizado
    me.update()
    # Modo Edit pra usar o operador de recálculo
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode='OBJECT')

# =========================
# EXECUÇÃO
# =========================

# limpar cena
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)

# coleção
coll = bpy.data.collections.new("ChaseTrackV3")
bpy.context.scene.collection.children.link(coll)

# gera programa + frames
prog   = program_from_blocks(NUM_BLOCKS)
frames = frames_from_program(prog)

# estrada
road = build_road(frames, coll)
postprocess(road)

# barreiras (opcional)
if BARRIERS:
    bL = build_barrier(frames, coll, side=-1)
    bR = build_barrier(frames, coll, side=+1)
    postprocess(bL); postprocess(bR)
    
if BUILD_PAD_ENABLE:
    padL = build_buildpad(frames, coll, side=-1)
    padR = build_buildpad(frames, coll, side=+1)
    postprocess(padL)
    postprocess(padR)

if TUNNEL_ENABLE:
    tun = build_tunnel(frames, coll)
    postprocess(tun)
    
if BUILDINGS_ENABLE:
    if BUILD_SIDE_L: build_buildings_along_pads(frames, coll, side=-1)
    if BUILD_SIDE_R: build_buildings_along_pads(frames, coll, side=+1)

if OBSTACLES_ENABLE:
    build_obstacles(frames, coll)

if BLOCK_AREAS_ENABLE:
    start_frame = frames[0]
    end_frame = frames[-1]

    # START
    if BLOCK_START_ENABLE:
        fwd, right, up = start_frame["fwd"], start_frame["right"], start_frame["up"]
        # centro da quadra
        center_start = start_frame["pos"] - fwd * (BLOCK_LENGTH * 0.5)
        build_block_area(center_start, fwd, right, up, coll, "Block_Start")

        if BLOCK_BARRIERS:
            barrier_center = center_start + fwd * (BLOCK_LENGTH * 0.5)  # agora fica dentro da quadra
            build_block_barrier(barrier_center, fwd, right, up, coll, is_start=True, name="Barrier_Start")

    # END
    if BLOCK_END_ENABLE:
        fwd, right, up = end_frame["fwd"], end_frame["right"], end_frame["up"]
        center_end = end_frame["pos"] + fwd * (BLOCK_LENGTH * 0.5)
        build_block_area(center_end, fwd, right, up, coll, "Block_End")

        if BLOCK_BARRIERS:
            barrier_center = center_end - fwd * (BLOCK_LENGTH * 0.5)  # idem, dentro da quadra
            build_block_barrier(barrier_center, fwd, right, up, coll, is_start=False, name="Barrier_End")

if SPAWN_ENABLE:
    build_spawn_points(frames[0], coll)

if CHECKPOINTS_ENABLE:
    build_checkpoints(frames, coll)


print("✅ v3: pista gerada com suavização de curva/pitch, banking gradual e largura variável.")


def split_mesh_by_vertex_and_lod(obj, map_name, vertex_limit=32767, lod_limit=200.0):
    """
    Divide o mesh em múltiplos objetos com no máximo vertex_limit vértices
    e com faces agrupadas espacialmente dentro de um alcance (lod_limit).
    Preserva materiais e índices de material.
    """
    import bpy, bmesh
    from mathutils import Vector

    if obj.type != 'MESH':
        print(f"⚠️ '{obj.name}' não é Mesh, ignorando split.")
        return []

    print(f"🔪 Dividindo '{obj.name}' (vértices: {len(obj.data.vertices)}) "
          f"com limite {vertex_limit} vértices e LOD {lod_limit}m...")

    # Aplica transformações
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

    mesh_data = obj.data
    bm = bmesh.new()
    bm.from_mesh(mesh_data)

    bm.faces.ensure_lookup_table()
    bm.verts.ensure_lookup_table()

    # Calcula centro de cada face
    face_centers = [(f, f.calc_center_median()) for f in bm.faces]
    # Ordena por posição (Z tem peso menor)
    face_centers.sort(key=lambda x: (x[1].x, x[1].y, x[1].z))

    processed_faces = set()
    split_objs = []
    part = 0

    while True:
        # encontra próxima face não processada
        next_face = None
        for f, center in face_centers:
            if f.index not in processed_faces:
                next_face = (f, center)
                break
        if not next_face:
            break  # tudo processado

        ref_face, ref_center = next_face
        group_faces = []
        group_verts = set()

        for f, center in face_centers:
            if f.index in processed_faces:
                continue

            dist = (center - ref_center).length
            if dist > lod_limit:
                continue  # muito longe

            verts_here = {v.index for v in f.verts}
            if len(group_verts | verts_here) > vertex_limit:
                continue

            group_faces.append(f)
            group_verts |= verts_here
            processed_faces.add(f.index)

        if not group_faces:
            processed_faces.add(ref_face.index)
            continue

        # cria novo BMesh temporário
        bm_group = bmesh.new()
        vert_map = {}

        # Cria vértices
        for f in group_faces:
            for v in f.verts:
                if v.index not in vert_map:
                    vert_map[v.index] = bm_group.verts.new(v.co)
        bm_group.verts.ensure_lookup_table()

        # Cria faces preservando o índice de material
        for f in group_faces:
            try:
                new_face = bm_group.faces.new([vert_map[v.index] for v in f.verts])
            except ValueError:
                # evita faces duplicadas
                continue
            if hasattr(f, "material_index"):
                new_face.material_index = f.material_index  # ✅ preserva material

        bm_group.normal_update()

        # Cria novo mesh e transfere o conteúdo
        new_mesh = bpy.data.meshes.new(f"{map_name}_split_{part}")
        bm.normal_update()
        bm_group.to_mesh(new_mesh)

        # ✅ Copia os materiais do objeto original
        for mat in obj.data.materials:
            new_mesh.materials.append(mat)

        # Cria novo objeto e linka à cena
        new_obj = bpy.data.objects.new(f"{map_name}_split_{part}", new_mesh)
        bpy.context.collection.objects.link(new_obj)
        split_objs.append(new_obj)

        print(f"✅ Criado: {new_obj.name} "
              f"({len(group_verts)} vértices, {len(group_faces)} faces, "
              f"centro ≈ {ref_center})")

        bm_group.free()
        part += 1

    bm.free()
    print(f"✨ Total de partes criadas: {len(split_objs)}")
    return split_objs


def _compute_anchor_world(obj, mode="median", use_selected=True):
    """
    Calcula a âncora em WORLD SPACE:
      - mode="median": média das posições dos vértices (ou selecionados)
      - mode="bounds": centro do bounding box da malha
    """
    mw = obj.matrix_world
    me = obj.data

    # Lê a malha via BMesh (funciona em Object ou Edit mode)
    if obj.mode == 'EDIT':
        bm = bmesh.from_edit_mesh(me)
        bm.verts.ensure_lookup_table()
        verts = [v for v in bm.verts if (v.select if use_selected else True)]
        if not verts: verts = list(bm.verts)
        if mode == "bounds":
            mins = Vector((verts[0].co.x, verts[0].co.y, verts[0].co.z))
            maxs = Vector((verts[0].co.x, verts[0].co.y, verts[0].co.z))
            for v in verts:
                co = v.co
                mins.x = min(mins.x, co.x); mins.y = min(mins.y, co.y); mins.z = min(mins.z, co.z)
                maxs.x = max(maxs.x, co.x); maxs.y = max(maxs.y, co.y); maxs.z = max(maxs.z, co.z)
            anchor_local = (mins + maxs) * 0.5
        else:
            acc = Vector((0,0,0))
            for v in verts: acc += v.co
            anchor_local = acc / len(verts)
    else:
        bm = bmesh.new(); bm.from_mesh(me); bm.verts.ensure_lookup_table()
        verts = list(bm.verts)
        if mode == "bounds":
            mins = Vector((verts[0].co.x, verts[0].co.y, verts[0].co.z))
            maxs = Vector((verts[0].co.x, verts[0].co.y, verts[0].co.z))
            for v in verts:
                co = v.co
                mins.x = min(mins.x, co.x); mins.y = min(mins.y, co.y); mins.z = min(mins.z, co.z)
                maxs.x = max(maxs.x, co.x); maxs.y = max(maxs.y, co.y); maxs.z = max(maxs.z, co.z)
            anchor_local = (mins + maxs) * 0.5
        else:
            acc = Vector((0,0,0))
            for v in verts: acc += v.co
            anchor_local = acc / len(verts)
        bm.free()

    # para WORLD
    anchor_world = mw @ anchor_local
    return anchor_world, anchor_local


def recenter_mesh_like_cursor_method(obj, anchor_mode="median", use_selected=True):
    """
    REPLICA o teu processo manual:
      1) (Edit) pega "cursor" = centro da malha (âncora);
      2) move todos os vértices pelo offset até a âncora ir para (0,0,0);
      3) (Object) posiciona o OBJETO na posição dessa âncora (preview idêntico).
    """
    if obj.type != 'MESH':
        print(f"❌ '{obj.name}' não é Mesh.")
        return None

    # 1) descobre a âncora (como o cursor no centro)
    anchor_world, anchor_local = _compute_anchor_world(obj, mode=anchor_mode, use_selected=use_selected)

    # 2) move vértices: âncora local -> (0,0,0)
    #    fazemos em BMesh para não depender de bpy.ops
    me = obj.data
    is_edit = (obj.mode == 'EDIT')

    if not is_edit:
        bm = bmesh.new(); bm.from_mesh(me)
    else:
        bm = bmesh.from_edit_mesh(me)

    bm.verts.ensure_lookup_table()
    for v in bm.verts:
        v.co -= anchor_local  # leva âncora local para origem

    if not is_edit:
        bm.to_mesh(me); bm.free()
    else:
        bmesh.update_edit_mesh(me, loop_triangles=False, destructive=False)

    # 3) coloca o OBJETO na posição da âncora (preview igual ao que você viu)
    obj.location = anchor_world
    # (mantemos rotação/escala como estão; é exatamente o que você faz no Object Mode)

    

    print(f"✅ '{obj.name}' recentrado via {anchor_mode}. Visual encaixado, mesh centrado.")
    return anchor_world

def create_transparent_texture(filepath, size=4):
    """Cria uma textura PNG totalmente transparente"""
    from PIL import Image
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    img.save(filepath)
    print(f"✅ Textura transparente criada em {filepath}")
    
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

def create_color_texture(filepath, color, size=400):
    """Cria uma textura PNG 1x1 (ou NxN) da cor RGBA especificada."""
    rgba = tuple(int(c*255) for c in color)
    img = Image.new("RGBA", (size, size), rgba)
    img.save(filepath)
    print(f"🎨 Textura de cor {color} criada em {filepath}")

def convert_colored_materials_to_principled(base_dir="//textures/"):
    """
    Garante que todos os materiais com cor base (não invisíveis)
    tenham um Principled BSDF com uma textura física de arquivo .png
    — ideal para exportar com Sollumz.
    """
    base_dir = bpy.path.abspath(base_dir)
    os.makedirs(base_dir, exist_ok=True)

    for mat in bpy.data.materials:
        if not mat.use_nodes:
            continue

        nodes = mat.node_tree.nodes
        links = mat.node_tree.links
        bsdf = next((n for n in nodes if n.type == "BSDF_PRINCIPLED"), None)
        if not bsdf:
            continue

        alpha = bsdf.inputs["Alpha"].default_value
        color = bsdf.inputs["Base Color"].default_value

        # ignorar os invisíveis (alpha == 0)
        if alpha <= 0.001:
            continue

        # Se já há textura de imagem ligada, ignora
        tex_node_linked = any(l.from_node.type == "TEX_IMAGE" for l in bsdf.inputs["Base Color"].links)
        if tex_node_linked:
            continue

        # cria arquivo .png com a cor base
        cname = mat.name.replace(" ", "_").lower()
        tex_path = os.path.join(base_dir, f"{cname}_color.png")
        if not os.path.exists(tex_path):
            create_color_texture(tex_path, color)

        # adiciona node de textura e conecta
        tex_node = nodes.new(type="ShaderNodeTexImage")
        tex_node.image = bpy.data.images.load(tex_path)
        tex_node.interpolation = 'Closest'
        links.new(tex_node.outputs["Color"], bsdf.inputs["Base Color"])

        # garante blend method apropriado
        mat.blend_method = 'OPAQUE'
        mat.use_backface_culling = True
        mat.diffuse_color = (color[0], color[1], color[2], 1.0)

        print(f"✅ Material '{mat.name}' agora possui textura física ({os.path.basename(tex_path)})")

    print("🧱 Conversão de materiais coloridos concluída.")

def join_all_meshes_before_split(map_name="map"):
    """
    Junta todos os objetos Mesh da cena em um único objeto.
    Retorna o novo objeto unificado.
    """
    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    if not meshes:
        print("⚠️ Nenhuma mesh encontrada para unir.")
        return None

    bpy.ops.object.select_all(action='DESELECT')
    for m in meshes:

        m.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]

    print(f"🧩 Unindo {len(meshes)} meshes...")
    bpy.ops.object.join()
    joined_obj = bpy.context.view_layer.objects.active
    joined_obj.name = f"{map_name}_joined"
    print(f"✅ Mesh unificada: {joined_obj.name}")
    return joined_obj

def export_splits_to_obj(map_name="track"):

    export_dir = os.path.abspath("D:\ExportGTA\saida\objs")
    os.makedirs(export_dir, exist_ok=True)

    split_objs = [o for o in bpy.data.objects if o.type == "MESH" and "_split_" in o.name]
    if not split_objs:
        print("⚠️ Nenhum objeto '_split_' encontrado para exportar.")
        return

    for obj in split_objs:
        # Seleciona apenas o objeto atual
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj

        # Caminho completo do arquivo
        filepath = os.path.join(export_dir, f"{obj.name}.obj")

        try:
            bpy.ops.wm.obj_export(
                filepath=filepath,
                export_selected_objects=True,
                forward_axis='NEGATIVE_Z',
                up_axis='Y',
                export_materials=False,
                path_mode='COPY',
            )
            print(f"✅ Exportado: {filepath}")
        except Exception as e:
            print(f"❌ Erro ao exportar {obj.name}: {e}")

    print(f"📦 Exportação finalizada ({len(split_objs)} arquivos) → {export_dir}")



PROPORTION_THRESHOLD = 0.01

def image_has_majority_transparency(img, proportion_threshold=0.05, alpha_cutoff=0.95):
    """
    Retorna True se a proporção de pixels realmente transparentes 
    (alpha < alpha_cutoff) for maior que proportion_threshold.
    
    proportion_threshold = fração mínima de pixels (ex.: 0.05 = 5%)
    alpha_cutoff = valor abaixo do qual consideramos pixel transparente
    """
    if not img or not img.has_data:
        return False

    if img.depth < 32:
        return False

    pixels = img.pixels[:]  # [R,G,B,A, R,G,B,A...]
    alpha_values = pixels[3::4]

    total = len(alpha_values)
    if total == 0:
        return False

    transparent = sum(1 for a in alpha_values if a < alpha_cutoff)
    proportion = transparent / total

    return proportion >= proportion_threshold

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
                    has_alpha = image_has_majority_transparency(node.image, proportion_threshold=PROPORTION_THRESHOLD, alpha_cutoff=0.95)
                    if has_alpha:
                        break

        if has_alpha:
            print(f"⚠️ '{mat.name}' usa textura com transparência → Aplicando Alpha flag")
            wm.sz_shader_material_index = 16 # DECAL
        else:
            print(f"✅ '{mat.name}' sem transparência → Aplicando Opaque flag")
            wm.sz_shader_material_index = 0  # DEFAULT

        # Seleciona material no slot atual
        obj.active_material_index = i

        # Converte somente este material
        bpy.ops.sollumz.convertmaterialtoselected()

    print(f"✅ Materiais de '{obj.name}' processados.")

def convert_collision_materials_with_alpha_flags(obj):
    """
    Converte cada material do objeto para material de colisão (Sollumz)
    e aplica flags de transparência se o material tiver alpha.
    """
    wm = bpy.data.window_managers["WinMan"]
    print(f"🎯 Convertendo materiais de colisão para '{obj.name}'...")

    if not obj.material_slots:
        print(f"⚠️ Objeto '{obj.name}' não tem materiais para converter.")
        return

    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj

    for i, slot in enumerate(obj.material_slots):
        mat = slot.material
        if not mat:
            continue

        has_alpha = False

        if mat.use_nodes:
            for node in mat.node_tree.nodes:
                if node.type == 'TEX_IMAGE' and node.image:
                    has_alpha = image_has_majority_transparency(
                        node.image, proportion_threshold=PROPORTION_THRESHOLD, alpha_cutoff=0.95
                    )
                    if has_alpha:
                        break

        obj.active_material_index = i
        print(f"🔧 Convertendo material '{mat.name}' (alpha={has_alpha})...")
        bpy.ops.sollumz.converttocollisionmaterial()

        # Garante que o material ativo seja o da colisão recém-criado
        active_mat = bpy.context.object.active_material
        if not active_mat or not hasattr(active_mat, "collision_flags"):
            continue

        # Aplica flags específicas
        if has_alpha:
            active_mat.collision_flags.see_through = True
            active_mat.collision_flags.shoot_through = True
            print(f"   ⚠️ Marcado como transparente (see_through + shoot_through)")
        else:
            active_mat.collision_flags.see_through = False
            active_mat.collision_flags.shoot_through = False
            print(f"   ✅ Marcado como sólido (sem transparência)")

    print(f"✅ Conversão de colisão concluída para '{obj.name}'.")


def process_sollumz_drawable_and_collision(obj):
    """
    Converte 'obj' (Mesh) em Drawable + cria cópia de colisão como Bound Composite,
    garantindo nome, parent e ordem mesmo se outros operadores trocarem o ativo.
    """
    import bpy

    if obj.type != 'MESH':
        print(f"⚠️ {obj.name} não é MESH. Ignorando.")
        return None

    # Nome base
    if obj.name.endswith("_export"):
        obj.name = obj.name.removesuffix("_export")
    base_name = obj.name

    # Aplica transforms ao visual
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

    # -----------------------------
    # 1) Criar cópia da colisão por API (sem bpy.ops.duplicate)
    # -----------------------------
    coll_target = obj.users_collection[0] if obj.users_collection else bpy.context.scene.collection
    col_obj = obj.copy()
    col_obj.data = obj.data.copy()
    col_obj.animation_data_clear()
    col_obj.name = f"{base_name}_Collision"
    # garanta que seja independente da hierarquia do visual
    col_obj.parent = None
    # link explícito
    coll_target.objects.link(col_obj)

    # -----------------------------
    # 2) Converter materiais de colisão + tipo Sollumz
    # -----------------------------
    col_obj.sollum_type = 'sollumz_bound_poly_triangle'
    bpy.ops.object.select_all(action='DESELECT')
    col_obj.select_set(True)
    bpy.context.view_layer.objects.active = col_obj
    convert_collision_materials_with_alpha_flags(col_obj)  # sua função
    print(f"✅ Colisão preparada: {col_obj.name}")

    # -----------------------------
    # 3) Converter o visual em Drawable (mantendo referência)
    # -----------------------------
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    obj.sollum_type = 'sollumz_drawable_model'
    obj.name = f"{base_name}_Model"

    convert_materials_with_alpha_flags(obj)  # sua função
    bpy.ops.sollumz.uv_maps_add_missing()
    bpy.ops.sollumz.color_attrs_add_missing()
    bpy.ops.sollumz.setallmatembedded()
    bpy.ops.sollumz.setallembedded()

    # ⚠️ Após essa chamada o objeto vira filho de uma Empty Drawable
    bpy.ops.sollumz.converttodrawable()
    drawable_empty = obj.parent
    if not drawable_empty or drawable_empty.sollum_type != 'sollumz_drawable':
        print("❌ Drawable Empty não encontrado após conversão!")
        return None

    drawable_empty.name = base_name
    print(f"📦 Drawable criado: {drawable_empty.name}")

    # -----------------------------
    # 4) Parent correto da colisão + converter para Composite
    # -----------------------------
    col_obj.parent = drawable_empty
    bpy.ops.object.select_all(action='DESELECT')
    col_obj.select_set(True)
    bpy.context.view_layer.objects.active = col_obj
    bpy.ops.sollumz.converttocomposite()

    print("✅ Hierarquia:")
    print(f"    Drawable → {drawable_empty.name}")
    print(f"    Visual   → {obj.name}")
    print(f"    Colisão  → {col_obj.name}")

    return drawable_empty


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
    return process_sollumz_drawable_and_collision(obj)

from sollumz.ytyp.operators.ytyp import get_selected_ytyp
from sollumz.sollumz_properties import ArchetypeType, AssetType, SollumType
from sollumz.tools.ytyphelper import has_collision, has_embedded_textures

def get_root_empties_by_prefix(prefix):
    """
    Retorna apenas as empties RAIZ (sem parent) cujo nome começa com o prefixo informado.
    Exemplo: 'Track_split_' → pega apenas Track_split_0, Track_split_1, etc.
    """
    roots = []
    for obj in bpy.data.objects:
        if obj.type == "EMPTY" and obj.name.startswith(prefix) and obj.parent is None:
            roots.append(obj)
    return roots


def create_ytyp_with_root_empties(map_name_prefix, map_name="TrackGen"):
    """
    Cria um YTYP e adiciona apenas as empties raiz (sem parent) como archetypes.
    Evita incluir objetos filhos como Collision ou BVH.
    """
    bpy.ops.object.select_all(action="DESELECT")

    # Coleta nomes das empties raiz antes do operador
    empty_names = [obj.name for obj in get_root_empties_by_prefix(map_name_prefix)]
    if not empty_names:
        print(f"⚠️ Nenhuma empty raiz encontrada com prefixo '{map_name_prefix}'.")
        return None

    print(f"🧱 Criando YTYP '{map_name}' com {len(empty_names)} empties raiz...")

    # Cria o YTYP
    bpy.ops.sollumz.createytyp()
    scene = bpy.context.scene
    scene.ytyp_index = len(scene.ytyps) - 1
    ytyp = scene.ytyps[scene.ytyp_index]
    ytyp.name = map_name

    scene.create_archetype_type = ArchetypeType.BASE
    created = 0

    # Reobtem as empties após a criação do YTYP
    for name in empty_names:
        obj = bpy.data.objects.get(name)
        if obj is None or obj.type != "EMPTY":
            print(f"⚠️ '{name}' não encontrado ou não é Empty, ignorando.")
            continue

        try:
            item = ytyp.new_archetype(scene.create_archetype_type)
            item.name = obj.name
            item.asset = obj
            item.texture_dictionary = obj.name if has_embedded_textures(obj) else ""

            # Verifica se pertence a um Drawable Dictionary
            drawable_dict = ""
            if obj.parent and obj.parent.sollum_type == SollumType.DRAWABLE_DICTIONARY:
                drawable_dict = obj.parent.name
            item.drawable_dictionary = drawable_dict

            # Se tiver colisão associada
            if has_collision(obj):
                item.physics_dictionary = obj.name

            item.asset_type = AssetType.DRAWABLE
            item.flags.flag6 = True  # Static
            item.flags.flag29 = True  # NPC avoid
            item.lod_dist = 500.0

            created += 1
        except Exception as e:
            print(f"❌ Erro ao adicionar archetype '{name}': {e}")

    print(f"✅ {created} archetypes raiz adicionados ao YTYP '{map_name}'.")
    return ytyp

def get_meshes_by_prefix(prefix):
    """
    Retorna apenas as empties RAIZ (sem parent) cujo nome começa com o prefixo informado.
    Exemplo: 'Track_split_' → pega apenas Track_split_0, Track_split_1, etc.
    """
    roots = []
    for obj in bpy.data.objects:
        if obj.type == "MESH" and obj.name.startswith(prefix) and obj.parent is None:
            roots.append(obj)
    return roots

def batch_process_objs(objs=None):
    prefix = MAP_NAME + "_split_"
    if objs == None:
        objs = get_meshes_by_prefix(prefix)
        
    print(f"🔄 Iniciando processamento de {len(objs)} objetos...")
    EMPTIES = []
    # Processa cada mesh importada
    for obj in objs:
        print(f"⚙️ Processando objeto '{obj.name}'...")
        try:
            EMPTIES.append(process_obj(obj))
        except Exception as e:
            print(f"❌ Erro ao processar {obj.name}: {e}")
            continue
    try:
        print(f"✅ Exportado com sucesso: {output_folder}")
    except Exception as e:
        print(f"⚠️ Erro: {e}")


    print("\n✅ Todos os arquivos processados com sucesso!")
    
    # Cria o YTYP com as empties Drawables acumuladas
    if 'EMPTIES' in locals() and EMPTIES:
        map_name = os.path.basename(os.path.normpath(output_folder))
        create_ytyp_with_root_empties(prefix, map_name=MAP_NAME)
        bpy.ops.object.select_all(action='DESELECT')
        emptiesObjs = get_root_empties_by_prefix(prefix)
        for empty in emptiesObjs:
            empty.select_set(True)
        bpy.ops.sollumz.exportytyp(directory=output_folder)
        save_as_gta(output_folder)
    else:
        print("⚠️ Nenhuma empty de Drawable foi coletada. YTYP não será criado.")

    print("📦 Todos os objetos permanecem na cena e foram adicionados ao YTYP.")


def recalc_normals_outside(obj):
    if obj.type != 'MESH':
        return
    me = obj.data
    # Garante cálculo atualizado
    me.update()
    # Modo Edit pra usar o operador de recálculo
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode='OBJECT')


# -----------------------------------------------------
# ⚙️ Pipeline automático de export
# -----------------------------------------------------
def process_track_for_export(map_name="map"):
    """
    1️⃣ Junta todas as meshes
    2️⃣ Divide por limite de vértices e LOD
    3️⃣ Exporta JSON de spawns e checkpoints
    """
    joined = join_all_meshes_before_split(map_name)
    if not joined:
        return

    print(f"✂️ Iniciando split de '{joined.name}' com LOD={LOD_LIMIT} e Vértices={VERTEX_LIMIT}...")
    parts = split_mesh_by_vertex_and_lod(joined, map_name, vertex_limit=VERTEX_LIMIT, lod_limit=LOD_LIMIT)

    print(f"🧭 Recentralizando {len(parts)} partes...")
    #skippedFirst = False
    for part in parts:
        #if not skippedFirst:
            #skippedFirst = True
            #continue
        recenter_mesh_like_cursor_method(part, use_selected=False)
    

    print(f"💾 Exportando JSON final para {OUTPUT_PATH}...")
    export_game_data(OUTPUT_PATH)
    print(f"🎉 Exportação concluída com sucesso!")
    for part in parts:
        part.location = Vector((0,0,0))
        #recalc_normals_outside(part)

    export_splits_to_obj(MAP_NAME)
    
    # 🚀 Executa
    batch_process_objs(objs=parts)
    

convert_invisible_materials_to_principled()
# Depois de rodar convert_invisible_materials_to_principled()
convert_colored_materials_to_principled(texture_dir)

process_track_for_export(MAP_NAME)