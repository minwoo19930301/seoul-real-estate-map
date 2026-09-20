"""Frame the actual editable City Hall MCP scene for inspection, without geometry edits."""
import bpy
from mathutils import Vector
for screen in bpy.data.screens:
 for area in screen.areas:
  if area.type=='VIEW_3D':
   space=area.spaces.active;space.shading.type='SOLID';space.shading.color_type='MATERIAL';space.shading.light='STUDIO';space.overlay.show_overlays=False
   space.region_3d.view_location=Vector((20,3,24));space.region_3d.view_distance=190;space.region_3d.view_rotation=bpy.data.objects['East_Photo'].rotation_euler.to_quaternion();space.region_3d.view_perspective='ORTHO'
print({'scene':bpy.context.scene.name,'meshes':sum(o.type=='MESH' for o in bpy.context.scene.objects),'camera':bpy.context.scene.camera.name})
