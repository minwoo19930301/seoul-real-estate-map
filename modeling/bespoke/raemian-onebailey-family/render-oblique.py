import bpy,json,math
from pathlib import Path
from mathutils import Vector
P=Path(__file__).resolve().parent
R=json.loads((P/'recipe.json').read_text());a=math.radians(R['angleDeg'])
def en(u,v,z):return (u*math.cos(a)-v*math.sin(a),u*math.sin(a)+v*math.cos(a),z)
c=bpy.data.cameras.new('123-122-oblique');o=bpy.data.objects.new('123-122-oblique',c);bpy.data.collections['REVIEW_ONLY_NOT_EXPORTED'].objects.link(o);o.location=en(20,-25,14);o.rotation_euler=(Vector(en(47,40,29))-o.location).to_track_quat('-Z','Y').to_euler();c.type='PERSP';c.lens=35
s=bpy.context.scene;s.camera=o;s.render.filepath=str(P/'review-family-123-122-oblique.png');bpy.ops.render.render(write_still=True)
bpy.ops.wm.save_as_mainfile(filepath=str(P/'raemian-onebailey-family.blend'))
p=P/'render-family-records.json';r=json.loads(p.read_text());r.append({'camera':o.name,'filepath':s.render.filepath,'position':list(o.location),'projection':c.type});p.write_text(json.dumps(r,indent=2));print('Added true oblique inspection, no geometry changes.')
