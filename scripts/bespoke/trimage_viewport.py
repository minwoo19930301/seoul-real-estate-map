"""Frame the complete isolated scene for actual Blender MCP viewport proof; do not save."""
import bpy
for c in bpy.data.collections:c.hide_render=False
scene=bpy.context.scene;scene.camera=bpy.data.objects['east-oblique']
for win in bpy.context.window_manager.windows:
 for a in win.screen.areas:
  if a.type=='VIEW_3D':
   a.spaces.active.region_3d.view_perspective='CAMERA';a.spaces.active.shading.type='MATERIAL';a.spaces.active.overlay.show_overlays=False
print('Complete4tower scene visible, camera framed; source blend not modified.')
