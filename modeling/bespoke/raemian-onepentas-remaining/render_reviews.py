from pathlib import Path
import bpy,json
from mathutils import Vector
P=Path(__file__).resolve().parent;s=bpy.context.scene;co=s.camera;s.render.image_settings.file_format='PNG';s.render.resolution_percentage=100;s.cycles.samples=16
views=[('Southeast_Street',(205,-290,86),(-10,-77,52),48),('South_Facades',(-45,-340,75),(-10,-80,54),48),('North_Courtyard',(-10,180,78),(-10,-78,55),48),('West_104',(-270,-100,65),(-25,-80,53),48),('Roof_Steps',(-85,-220,340),(-10,-78,55),42),('Skycommunity',(110,-205,130),(25,-75,89),66)]
for name,eye,target,lens in views:
 co.location=eye;co.rotation_euler=(Vector(target)-co.location).to_track_quat('-Z','Y').to_euler();co.data.lens=lens;s.render.resolution_x=1400;s.render.resolution_y=1100;s.render.filepath=str(P/('review-'+name+'.png'));bpy.ops.render.render(write_still=True)
print('Six MCP render views completed; saved sourceblend unchanged')
