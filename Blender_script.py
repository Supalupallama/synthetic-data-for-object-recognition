import bpy
import math
import random
import mathutils
import bpy_extras.object_utils
from mathutils import Vector
import time

rendering = True

def move_car_to_position(area_index, car_index):
    car_collection_name = f"car_{car_index}"
    position_index = random.randint(0, 2)  
    position_name = f"cam_{area_index}_{position_index}"
    car_collection = bpy.data.collections["Cars"].children.get(car_collection_name)
    
    env_collection_name = f"env_{area_index}"
    car_pos_collection_name = f"car_pos_{area_index}"

    
    env_collection = bpy.data.collections.get(env_collection_name)
    if not env_collection:
        print(f"Environment collection '{env_collection_name}' not found!")
        return
    
    car_pos_collection = env_collection.children.get(car_pos_collection_name)
    if not car_pos_collection:
        print(f"Car position collection '{car_pos_collection_name}' not found in '{env_collection_name}'!")
        return
    
    position_object = car_pos_collection.objects.get(position_name)
    if not position_object:
        print(f"Position object '{position_name}' not found in '{car_pos_collection_name}'!")
        return


    if not car_collection:
        print(f"Car collection '{car_collection_name}' not found!")
        return

    target_location = position_object.matrix_world.translation
    target_rotation = position_object.matrix_world.to_euler()
    random_rotation_z = random.uniform(0, 2*math.pi)
    random_rotation = (0, 0, random_rotation_z)

    for obj in car_collection.all_objects:
        if obj.parent is None:  
            obj.location = target_location
            obj.rotation_euler = random_rotation

    bpy.context.view_layer.update()

    move_camera_to_point_at(target_location, area_index, position_index)

def move_camera_to_point_at(target_location, area_index, position_index, skew_factor=23, offset_range=8):
    r = random.uniform(5, 80) #mabe less
    theta = random.uniform(0, 2 * math.pi)  # Angle in the XY plane
    phi = math.pi / 2 - random.betavariate(2, skew_factor) * (math.pi / 2) #skew probailites down

    # Convert spherical coordinates to cartesian coordinates so it works
    x = r * math.sin(phi) * math.cos(theta)
    y = r * math.sin(phi) * math.sin(theta)
    z = r * math.cos(phi)

    camera = bpy.data.objects['Camera']
    camera.location = target_location + mathutils.Vector((x, y, z)) 

    # Adjust offset range based on distance
    distance = (camera.location - target_location).length
    adjusted_offset_range = offset_range * (distance / 80)  # Scale offset properly fixed

    # offset for trainings
    offset_x = random.uniform(-adjusted_offset_range, adjusted_offset_range)
    offset_y = random.uniform(-adjusted_offset_range, adjusted_offset_range)
    offset_z = random.uniform(-adjusted_offset_range, adjusted_offset_range)
    adjusted_target_location = target_location + mathutils.Vector((offset_x, offset_y, offset_z))

    direction = camera.location - adjusted_target_location 
    rot_quat = direction.to_track_quat('Z', 'Y')
    camera.rotation_euler = rot_quat.to_euler()

def set_sun_rotation():
    sun = bpy.data.objects['Sun']
    sun.rotation_euler = (
        random.uniform(0, math.pi),  
        random.uniform(0, math.pi),  
        random.uniform(0, 2*math.pi)  
    )

def create_volume_scatter_cube(car_location, camera_location):
    cube = bpy.data.objects.get("fog")
    if not cube:
        print("Cube named 'fog' not found!")
        return

    mat = bpy.data.materials.get("VolumeScatterMaterial")
    if not mat:
 
        mat = bpy.data.materials.new(name="VolumeScatterMaterial")
        mat.use_nodes = True
        nodes = mat.node_tree.nodes
        links = mat.node_tree.links

        for node in nodes:
            nodes.remove(node)


        volume_scatter = nodes.new(type='ShaderNodeVolumeScatter')
        volume_scatter.location = (0, 0)

        material_output = nodes.new(type='ShaderNodeOutputMaterial')
        material_output.location = (200, 0)
        links.new(volume_scatter.outputs['Volume'], material_output.inputs['Volume'])
    else:
        nodes = mat.node_tree.nodes
        volume_scatter = nodes.get('Volume Scatter')

    distance = (car_location - camera_location).length

    base_density = random.uniform(0.05, 0.9) # make smaller
    
    density = base_density * (1 / ( 2*distance / 10)) 
    volume_scatter.inputs['Density'].default_value = density

    cube.data.materials.clear() 
    cube.data.materials.append(mat)

def calculate_yolo_bbox(obj, camera, scene):
    coords = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
        #(normalized to 0-1 screen space) understand better
    coords_2d = [bpy_extras.object_utils.world_to_camera_view(scene, camera, coord) for coord in coords]

    x_coords = [c.x for c in coords_2d]
    y_coords = [1 - c.y for c in coords_2d]  # yolo-formate

    x_min, x_max = min(x_coords), max(x_coords)
    y_min, y_max = min(y_coords), max(y_coords)
    
     #clamp the vals
    x_min = max(0, min(1, x_min))
    x_max = max(0, min(1, x_max))
    y_min = max(0, min(1, y_min))
    y_max = max(0, min(1, y_max))
    
 # YOLO format: class_id, x_center, y_center, width, height (all normalized)
    x_center = (x_min + x_max) / 2
    y_center = (y_min + y_max) / 2
    width = x_max - x_min
    height = y_max - y_min
    
    return x_center, y_center, width, height

def export_yolo_annotation(frame_number, car_index, area_index, output_folder="/Users/tom/Documents/Code/Python/Jugend_forscht/data_out/labels"):
    output_folder = bpy.path.abspath(output_folder)
    
    if car_index < 4:
        camera = bpy.data.objects['Camera']
        scene = bpy.context.scene
        
        car_collection_name = f"car_{car_index}"
        car_collection = bpy.data.collections["Cars"].children.get(car_collection_name)
        if not car_collection:
            print(f"Collection '{car_collection_name}' not found!")
            return
        
        bounding_box_name = f"bounding_b_{car_index}"
        cube_obj = car_collection.objects.get(bounding_box_name)

        if not cube_obj:
            print(f"BoundingBox '{bounding_box_name}' not found in the car collection!")
            return
        
        x_center, y_center, width, height = calculate_yolo_bbox(cube_obj, camera, scene)
        
        yolo_line = f"0 {x_center} {y_center} {width} {height}"
    else:
        yolo_line = ""

    annotation_file = f"{output_folder}/frame_{area_index}_{car_index}_{frame_number:03d}.txt"
    
    # Write the annotation to a file
    with open(annotation_file, "w") as f:
        f.write(yolo_line + "\n")

def render_frame(frame_number, car_index, area_index):
    bpy.context.scene.frame_set(frame_number)
    bpy.context.scene.render.image_settings.file_format = 'JPEG'
    image_file = f"/Users/tom/Documents/Code/Python/Jugend_forscht/data_out/images/frame_{area_index}_{car_index}_{frame_number:03d}.jpeg"
    bpy.context.scene.render.filepath = image_file
    bpy.ops.render.render(write_still=True)
    export_yolo_annotation(frame_number, car_index, area_index)

def update(car_location, camera_location):
    set_sun_rotation()
    create_volume_scatter_cube(car_location, camera_location)    

def set_car_collections_rendering(car_index):
    cars = [f"car_{i}" for i in range(4)]
    for i, car in enumerate(cars):
        car_collection = bpy.data.collections["Cars"].children.get(car)
        if car_collection:
            car_collection.hide_render = (i != car_index)

def set_environment_collections_rendering(area_index):
    for i in range(2):
        env_collection = bpy.data.collections.get(f"env_{i}")
        if env_collection:
            env_collection.hide_render = (i != area_index)

if rendering:
    total_start_time = time.time()
    per_class_time = {}
    per_area_time = {}

    total_frames = 30
    cars = [f"car_{i}" for i in range(4)]
    frames_per_area = total_frames // 2  
    frames_per_car = frames_per_area // (len(cars) + 1)  # +1 for negative examples

    print(f"Rendering a total of: {total_frames} images, with: {frames_per_car} frames per car and {frames_per_area} per enviroment")

    processed_frames = 0

    for area_index in range(2):  
        area_start_time = time.time()
        set_environment_collections_rendering(area_index)  # Set env collection rendering
        print(f"Rendering {frames_per_area} frames for area {area_index}")

        for car_index in range(len(cars) + 1):
            class_start_time = time.time()

            for frame in range(frames_per_car):
                if car_index < len(cars):
                    set_car_collections_rendering(car_index)
                    move_car_to_position(area_index, car_index)
                    car_location = bpy.data.collections["Cars"].children[cars[car_index]].all_objects[0].location
                else:
                    set_car_collections_rendering(-1)
                    random_target_location = mathutils.Vector((random.uniform(-5, 5), random.uniform(-5, 5), 0))
                    move_camera_to_point_at(random_target_location, area_index, random.randint(0, 2))
                    car_location = random_target_location

                camera_location = bpy.data.objects['Camera'].location
                update(car_location, camera_location)
                render_frame(frame, car_index, area_index)

                processed_frames += 1
                progress_percent = (processed_frames / total_frames) * 100
                elapsed_time = time.time() - total_start_time
                average_time_per_frame = elapsed_time / processed_frames
                remaining_frames = total_frames - processed_frames
                estimated_remaining_time = remaining_frames * average_time_per_frame / 60  

                print(f"Progress: {processed_frames}/{total_frames} frames [{progress_percent:.2f}%]")
                print(f"Estimated remaining time: {estimated_remaining_time:.2f} minutes")

            per_class_time[car_index] = per_class_time.get(car_index, 0) + (time.time() - class_start_time)

        per_area_time[area_index] = time.time() - area_start_time

    total_end_time = time.time()
    total_time_minutes = (total_end_time - total_start_time) / 60
    print(f"Total time: {total_time_minutes:.2f} minutes")
    
    for index, duration in per_class_time.items():
        duration_minutes = duration / 60
        print(f"Class {index} time: {duration_minutes:.2f} minutes")
    
    for index, duration in per_area_time.items():
        duration_minutes = duration / 60
        print(f"Area {index} time: {duration_minutes:.2f} minutes")