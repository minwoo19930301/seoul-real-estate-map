from pathlib import Path
import bpy,json
from mathutils import Vector
P=Path(__file__).resolve().parent;s=bpy.context.scene;co=s.camera;s.render.image_settings.file_format='PNG';s.render.resolution_percentage=100
views=[('Official_NE',(190,125,70),(-33,-13,59),45,(1600,1350)),('North_River',(-15,205,70),(-35,-12,59),48,(1600,1350)),('South_Courtyard',(-55,-275,68),(-35,-12,57),48,(1600,1350)),('West_Low105',(-240,20,55),(-66,-20,55),47,(1500,1400)),('East_106',(205,32,42),(0,-2,57),48,(1300,1600)),('Roof_Arms',(-75,-165,255),(-35,-12,45),48,(1600,1400))]
views.append(('106_Base_Photo04',(65,54,10),(13,11,13),52,(1500,1200)))
for name,eye,target,lens,size in views:
 co.location=eye;co.rotation_euler=(Vector(target)-co.location).to_track_quat('-Z','Y').to_euler();co.data.lens=lens;s.render.resolution_x,s.render.resolution_y=size;s.render.filepath=str(P/('review-'+name+'.png'));bpy.ops.render.render(write_still=True)
print('Rendered six site-specificcomparisonviews; blendunchanged.')
