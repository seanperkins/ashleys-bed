"""Build Rockler's horizontal queen I-Semble cabinet in Autodesk Fusion.

Cabinet stock dimensions: Rockler horizontal-murphy-bed-inst-25.pdf, page 6.
Mounting-plate insert pilots and lower door-bracket pilots: pages 8 and 17.
Hardware envelopes and pivot locations remain REPRESENTATIVE, not manufacturing
geometry. This model is not a substitute for the kit's installation manual.
Run from Fusion's Scripts and Add-Ins dialog. Outputs are saved beside this
script's folder, in output/. No existing Fusion documents are modified.
"""
import adsk.core
import adsk.fusion
import csv
import json
import math
from pathlib import Path
import traceback

IN = 2.54  # Fusion's internal length unit is centimetres.
HERE = Path(__file__).resolve().parent
OUT = HERE.parent / 'output'
SOURCE = 'https://go.rockler.com/tech/horizontal-murphy-bed-inst-25.pdf'
W, H, D, T = 86.75, 64.0, 16.0, 0.75
SIDE_W = 30.0
NAVY = (24, 43, 73)
PX, PY, PZ = 0.0, 15.5, 11.4375
DOOR_W, DOOR_H, DOOR_GAP = 21.125, 61.8125, 0.125
DOOR_Y = 1.09375 - PZ
FRAME_Y0, FRAME_Y1 = -9.8, 51.2
LEG_Y, LEG_Z = 50.5, 0.8
LEG_LENGTH = PZ + LEG_Z
# Representative gas springs: fixed cabinet end, bed end offset from the pivot in bed coordinates.
# The cylinder and rod keep their lengths; only the rod's exposed length changes with bed angle.
PISTON_X_INSET = 1.2
PISTON_FIXED_YZ = (6.5625, 29.0)
PISTON_BED_YZ = (-7.5, 0.8)
GAS_CYLINDER_LENGTH, GAS_ROD_LENGTH = 14.0, 13.5


def point(x, y, z):
    return adsk.core.Point3D.create(x * IN, y * IN, z * IN)


def value(n):
    return adsk.core.ValueInput.createByReal(n * IN)


def component(parent, name, origin=(0, 0, 0)):
    transform = adsk.core.Matrix3D.create()
    transform.translation = adsk.core.Vector3D.create(*(v * IN for v in origin))
    occurrence = parent.occurrences.addNewComponent(transform)
    occurrence.component.name = name
    return occurrence


def dimensioned_box(comp, name, xyz, size, appearance, material=None):
    """An editable, dimensioned rectangular sketch and extrusion."""
    x, y, z = xyz
    sx, sy, sz = size
    plane_input = comp.constructionPlanes.createInput()
    plane_input.setByOffset(comp.xYConstructionPlane, value(z))
    plane = comp.constructionPlanes.add(plane_input)
    plane.name = name + ' | elevation'
    plane.isLightBulbOn = False
    sketch = comp.sketches.add(plane)
    sketch.name = name + ' | footprint (inches)'
    lines = sketch.sketchCurves.sketchLines.addTwoPointRectangle(
        point(x, y, 0), point(x + sx, y + sy, 0))
    lines.item(0).startSketchPoint.isFixed = True
    dims = sketch.sketchDimensions
    dims.addDistanceDimension(lines.item(0).startSketchPoint,
                              lines.item(0).endSketchPoint,
                              adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation,
                              point(x + sx / 2, y - 1, 0))
    dims.addDistanceDimension(lines.item(1).startSketchPoint,
                              lines.item(1).endSketchPoint,
                              adsk.fusion.DimensionOrientations.VerticalDimensionOrientation,
                              point(x + sx + 1, y + sy / 2, 0))
    extrude_input = comp.features.extrudeFeatures.createInput(
        sketch.profiles.item(0), adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
    extrude_input.setOneSideExtent(adsk.fusion.DistanceExtentDefinition.create(value(sz)),
                                  adsk.fusion.ExtentDirections.PositiveExtentDirection)
    feature = comp.features.extrudeFeatures.add(extrude_input)
    feature.name = name
    body = feature.bodies.item(0)
    body.name = name
    if material is not None:
        body.material = material
    body.appearance = appearance
    sketch.isLightBulbOn = False
    return body


class Hardware:
    """Native editable solids in one base feature per hardware component."""
    def __init__(self, comp, appearance):
        self.comp = comp
        self.appearance = appearance
        self.temp = adsk.fusion.TemporaryBRepManager.get()
        self.base = comp.features.baseFeatures.add()
        self.base.name = 'Representative hardware geometry — measure actual kit'
        self.base.startEdit()

    def add(self, temp_body, name, appearance=None):
        if temp_body is None:
            raise RuntimeError('Solid creation failed: ' + name)
        body = self.comp.bRepBodies.add(temp_body, self.base)
        body.name = name
        body.appearance = appearance or self.appearance
        return body

    def box(self, name, xyz, size, appearance=None):
        x, y, z = xyz
        sx, sy, sz = size
        obb = adsk.core.OrientedBoundingBox3D.create(
            point(x + sx / 2, y + sy / 2, z + sz / 2),
            adsk.core.Vector3D.create(1, 0, 0), adsk.core.Vector3D.create(0, 1, 0),
            sx * IN, sy * IN, sz * IN)
        return self.add(self.temp.createBox(obb), name, appearance)

    def rod(self, name, a, b, radius, appearance=None):
        return self.add(self.temp.createCylinderOrCone(point(*a), radius * IN,
                                                      point(*b), radius * IN),
                        name, appearance)

    def finish(self):
        self.base.finishEdit()


def appearance(design, library, name, rgb):
    base = library.appearances.itemByName('Plastic - Matte (White)')
    if base is None:
        raise RuntimeError('Fusion matte-white appearance template is unavailable')
    app = design.appearances.addByCopy(base, name)
    color = adsk.core.ColorProperty.cast(app.appearanceProperties.itemById('opaque_albedo'))
    color.value = adsk.core.Color.create(*rgb, 255)
    return app


def revolute(root, fixed, moving, name, pivot):
    sketch = root.sketches.add(root.xYConstructionPlane)
    sketch.name = name + ' | representative pivot'
    p = sketch.sketchPoints.add(point(*pivot))
    p.isFixed = True
    geometry = adsk.fusion.JointGeometry.createByPoint(p)
    joint_input = root.asBuiltJoints.createInput(moving, fixed, geometry)
    joint_input.setAsRevoluteJointMotion(adsk.fusion.JointDirections.XAxisJointDirection)
    joint = root.asBuiltJoints.add(joint_input)
    joint.name = name
    joint.isLightBulbOn = False
    sketch.isLightBulbOn = False
    return joint


def camera(app, target, eye, filename=None):
    viewport = app.activeViewport
    cam = viewport.camera
    cam.viewOrientation = adsk.core.ViewOrientations.ArbitraryViewOrientation
    cam.cameraType = adsk.core.CameraTypes.OrthographicCameraType
    cam.target = point(*target)
    cam.eye = point(*eye)
    cam.upVector = adsk.core.Vector3D.create(0, 0, 1)
    cam.isFitView = True
    cam.isSmoothTransition = False
    viewport.camera = cam
    viewport.refresh()
    adsk.doEvents()
    if filename is not None and not viewport.saveAsImageFile(str(OUT / filename), 1800, 1400):
        raise RuntimeError('Fusion viewport export failed: ' + filename)


def body_dimensions(body):
    bb = body.boundingBox
    return [(getattr(bb.maxPoint, k) - getattr(bb.minPoint, k)) / IN for k in 'xyz']


def verify_dimensions(body, expected):
    actual = body_dimensions(body)
    if any(abs(a - e) > 0.0001 for a, e in zip(actual, expected)):
        raise RuntimeError(f'{body.name}: expected {expected} inches, got {actual}')
    return actual


def drill_pilots(comp, body, name, base_plane, offset, centers, diameter, depth, direction):
    """Cut only pilot locations explicitly dimensioned in the current manual."""
    plane_input = comp.constructionPlanes.createInput()
    plane_input.setByOffset(base_plane, value(offset))
    plane = comp.constructionPlanes.add(plane_input)
    plane.name = name+' | drilling plane'
    plane.isLightBulbOn = False
    sketch = comp.sketches.add(plane)
    sketch.name = name+' | exact centers'
    for xyz in centers:
        sketch.sketchCurves.sketchCircles.addByCenterRadius(
            sketch.modelToSketchSpace(point(*xyz)), diameter*IN/2)
    profiles = adsk.core.ObjectCollection.create()
    for profile in sketch.profiles:
        profiles.add(profile)
    cut = comp.features.extrudeFeatures.createInput(profiles, adsk.fusion.FeatureOperations.CutFeatureOperation)
    positive = plane.geometry.normal.dotProduct(adsk.core.Vector3D.create(*direction)) > 0
    cut.setOneSideExtent(adsk.fusion.DistanceExtentDefinition.create(value(depth)),
                         adsk.fusion.ExtentDirections.PositiveExtentDirection if positive
                         else adsk.fusion.ExtentDirections.NegativeExtentDirection)
    before = body.volume
    feature = comp.features.extrudeFeatures.add(cut)
    feature.name = name
    sketch.isLightBulbOn = False
    removed = before-body.volume
    expected = len(centers)*math.pi*(diameter*IN/2)**2*depth*IN
    if abs(removed-expected) > max(1e-7, expected*1e-6):
        raise RuntimeError(f'{name}: pilot cut volume disagrees with specified diameter/depth')
    return {'count': len(centers), 'diameterInches': diameter, 'depthInches': depth,
            'removedCubicInches': removed/IN**3}


def build_side_cabinet(root, plywood, navy, natural, black, cutlist, side, origin_x):
    # Viewed from the room (+Y), negative X is the right-hand side.
    occurrence = component(root, f'05 {side} bookcase | 30 x 64 x 16 | plywood', (origin_x, 0, 0))
    occurrence.isGrounded = True
    cabinet = occurrence.component
    parts = []

    def panel(name, xyz, size, cut_size, owner=cabinet, finish=navy):
        body = dimensioned_box(owner, name, xyz, size, finish, plywood)
        parts.append((body, size))
        cutlist.append([f'{side} cabinet: {name.removeprefix("SC ")}', 1, *cut_size,
                        'Project side cabinet design; not Rockler kit'])
        return body

    clear_width = SIDE_W - 2*T
    back_t = 0.25
    bottom_z = 2.5
    drawer_shelf_z = 14.0
    panel('SC Left side', (0, 0, 0), (T, D, H), (T, D, H))
    panel('SC Right side', (SIDE_W-T, 0, 0), (T, D, H), (T, D, H))
    panel('SC Top', (T, 0, H-T), (clear_width, D, T), (T, D, clear_width))
    panel('SC Bottom', (T, 0, bottom_z), (clear_width, D, T), (T, D, clear_width))
    panel('SC Recessed plinth', (T, D-2*T, 0), (clear_width, T, bottom_z),
          (T, bottom_z, clear_width))
    back_height = H-T-bottom_z-T
    panel('SC Plywood back', (T, 0, bottom_z+T), (clear_width, back_t, back_height),
          (back_t, clear_width, back_height))
    panel('SC Shelf above drawer', (T, back_t, drawer_shelf_z),
          (clear_width, D-back_t, T), (T, D-back_t, clear_width))
    opening_height = (H-T-(drawer_shelf_z+T)-3*T)/4
    for index in range(3):
        z = drawer_shelf_z+T+opening_height+index*(opening_height+T)
        panel(f'SC Shelf {index+1}', (T, back_t, z),
              (clear_width, D-back_t, T), (T, D-back_t, clear_width))

    drawer_occ = component(cabinet, '06 Bottom drawer | plywood box | closed')
    drawer_occ.isGroundToParent = True
    drawer = drawer_occ.component
    drawer.attributes.add('ProjectDesign', 'drawer',
                          'Closed plywood box. 1/2 inch clearance per side reserved for slides; '
                          'select actual slides and joinery before fabrication.')
    box_x, box_y, box_z = T+0.5, 1.25, 4.0
    box_w, box_d, box_h, box_t = clear_width-1.0, 14.0, 8.0, 0.5
    for label, x in [('Left', box_x), ('Right', box_x+box_w-box_t)]:
        panel('SC Drawer '+label+' side', (x, box_y, box_z), (box_t, box_d, box_h),
              (box_t, box_h, box_d), drawer, natural)
    for label, y in [('back', box_y), ('inner front', box_y+box_d-box_t)]:
        panel('SC Drawer '+label, (box_x+box_t, y, box_z), (box_w-2*box_t, box_t, box_h),
              (box_t, box_h, box_w-2*box_t), drawer, natural)
    panel('SC Drawer bottom', (box_x, box_y, box_z-0.25), (box_w, box_d, 0.25),
          (0.25, box_d, box_w), drawer, natural)
    face_z = bottom_z+T+0.125
    face_h = drawer_shelf_z-0.125-face_z
    panel('SC Drawer face', (T+0.125, D-T, face_z), (clear_width-0.25, T, face_h),
          (T, face_h, clear_width-0.25), drawer)
    pull = Hardware(drawer, black)
    pull_z = face_z+face_h/2
    pull.rod('Drawer pull — representative', (SIDE_W/2-3, D+0.75, pull_z),
             (SIDE_W/2+3, D+0.75, pull_z), 0.125)
    for x in [SIDE_W/2-3, SIDE_W/2+3]:
        pull.rod('Drawer pull standoff', (x, D, pull_z), (x, D+0.75, pull_z), 0.125)
    pull.finish()
    for body, size in parts:
        verify_dimensions(body, size)
    bounds = occurrence.preciseBoundingBox
    if (abs(bounds.minPoint.x/IN-origin_x) > 0.0001
            or abs(bounds.maxPoint.x/IN-(origin_x+SIDE_W)) > 0.0001):
        raise RuntimeError(f'{side} bookcase must span x={origin_x} to {origin_x+SIDE_W} inches')
    return {
        'carcassInchesWHD': [SIDE_W, H, D],
        'positionInchesX': [origin_x, origin_x+SIDE_W],
        'openBays': 4,
        'clearBayHeightInches': opening_height,
        'drawerBoxes': 1,
        'material': plywood.name,
        'constructionScope': 'Plywood parts and closed drawer layout; slides, shelf supports and joinery not detailed',
        'partsInchesXYZ': {body.name: body_dimensions(body) for body, _ in parts},
    }


def run(context):
    OUT.mkdir(exist_ok=True)
    result = {'status': 'running', 'source': SOURCE,
              'hardwareAccuracy': 'Cabinet cuts and specified pilot locations are manual-sourced. '
                                  'Hardware envelopes and pivot placement remain representative; not exact kit CAD.',
              'files': []}
    status_file = OUT / 'build-result.json'
    status_file.write_text(json.dumps(result, indent=2))
    try:
        app = adsk.core.Application.get()
        doc = app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
        doc.name = 'Ashley — navy plywood Murphy bed and left bookcase'
        design = adsk.fusion.Design.cast(app.activeProduct)
        design.designType = adsk.fusion.DesignTypes.ParametricDesignType
        design.fusionUnitsManager.distanceDisplayUnits = adsk.fusion.DistanceUnits.InchDistanceUnits
        root = design.rootComponent
        root.attributes.add('RocklerReference', 'manual', SOURCE)
        root.attributes.add('RocklerReference', 'accuracy', result['hardwareAccuracy'])
        root.attributes.add('RocklerReference', 'installation',
                            'Follow Rockler manual. Retain BOTH headboards. Plywood, not MDF. '
                            'Anchor to at least 3 wooden studs with ALL specified fasteners. '
                            'Mattress and dynamic weights must satisfy manual p3. No structural certification.')
        library = app.materialLibraries.itemByName('Fusion Appearance Library')
        if library is None:
            raise RuntimeError('Fusion appearance library is unavailable')
        wood = appearance(design, library, 'Painted plywood — dark navy #182B49', NAVY)
        face = wood
        natural = appearance(design, library, 'Plywood drawer interior — natural', (217, 191, 151))
        plywood = app.materialLibraries.itemByName('Fusion Material Library').materials.itemByName('Plywood, Finish')
        if plywood is None:
            raise RuntimeError('Fusion finish-plywood physical material is unavailable')
        black = appearance(design, library, 'Kit steel — satin charcoal', (40, 43, 46))
        silver = appearance(design, library, 'Piston rod — silver', (172, 180, 187))
        slat_color = appearance(design, library, 'Cambered beech slats — representative', (225, 198, 148))
        fabric = appearance(design, library, 'Queen mattress — ivory', (234, 232, 221))

        cabinet_occ = component(root, '01 Cabinet | Rockler-dimensioned plywood parts')
        cabinet = cabinet_occ.component
        cutlist = []
        cabinet_bodies = []
        def panel(name, xyz, size, cut_size):
            body = dimensioned_box(cabinet, name, xyz, size, wood, plywood)
            cabinet_bodies.append((body, size))
            cutlist.append([name, 1, *cut_size, 'Rockler manual p6'])
            return body
        panel('1R Right side | 3/4 x 16 x 64', (0, 0, 0), (T, D, H), (T, D, H))
        panel('1L Left side | 3/4 x 16 x 64', (W - T, 0, 0), (T, D, H), (T, D, H))
        panel('2T Top | 3/4 x 16 x 85-1/4', (T, 0, H - T), (W - 2*T, D, T), (T, D, W - 2*T))
        panel('2B Bottom | 3/4 x 16 x 85-1/4', (T, 0, 0), (W - 2*T, D, T), (T, D, W - 2*T))
        panel('3 Upper headboard — REQUIRED', (T, 0, H - T - 16), (W - 2*T, T, 16), (T, 16, W - 2*T))
        panel('4 Lower headboard — REQUIRED', (T, 0, T), (W - 2*T, T, 16), (T, 16, W - 2*T))
        panel('6 Permanent stop | adjust contact location to actual kit', ((W-56)/2, 11.125, H-T-0.625),
              (56, 3, 0.625), (0.625, 3, 56))
        cabinet_occ.isGrounded = True
        # Page 8: distances from the FRONT edge and the cabinet side's BOTTOM edge.
        mounting_centers = [
            (3.125, 11.4375), (3.125, 13.875), (6.9375, 17.6875),
            (9.4375, 11.4375), (9.4375, 17.6875), (9.4375, 25.25),
            (9.4375, 27.75), (9.4375, 30.25),
        ]
        result['manufacturerPilotCuts'] = {}
        for index, (label, x, direction) in enumerate([
            ('Right', T, (-1, 0, 0)), ('Left', W-T, (1, 0, 0)),
        ]):
            result['manufacturerPilotCuts'][label+' mounting plate — p8'] = drill_pilots(
                cabinet, cabinet_bodies[index][0], label+' mounting plate insert pilots | Rockler p8',
                cabinet.yZConstructionPlane, x,
                [(x, D-front, height) for front, height in mounting_centers],
                27/64, 9/16, direction)

        fixed_hardware_occ = component(cabinet, 'Mounting plates | REPRESENTATIVE')
        fixed_hardware_occ.isGroundToParent = True
        fixed = Hardware(fixed_hardware_occ.component, black)
        for label, x in [('L', T), ('R', W-T-0.1875)]:
            fixed.box(label + ' mounting plate upright', (x, 5.75, 10.3), (0.1875, 1.7, 21))
            fixed.box(label + ' mounting plate base', (x, 5.75, 10.3), (0.1875, 9.7, 1.5))
            fixed.rod(label + ' pivot saddle / bearing', (x, PY, PZ), (x+0.5, PY, PZ), 0.5)
        fixed.finish()
        wall_occ = component(cabinet, 'Wall brackets | HIDDEN REFERENCE — Rockler p12')
        wall_occ.isGroundToParent = True
        wall_occ.component.attributes.add('RocklerReference', 'visibility',
                                          'Hidden for design review at user request; retained for installation reference. '
                                          'Hiding does not replace the specified wall anchoring.')
        wall = Hardware(wall_occ.component, black)
        for i, x in enumerate([19.375, 43.375, 67.375], 1):
            wall.box(f'HH{i} top bracket — PLACE AT ACTUAL STUD', (x-0.75, 0, H), (1.5, 5, 0.125))
            wall.box(f'HH{i} wall flange — PLACE AT ACTUAL STUD', (x-0.75, 0, H), (1.5, 0.125, 2.5))
        wall.finish()
        wall_occ.isLightBulbOn = False
        result['wallBrackets'] = 'Retained as hidden reference in Fusion; excluded from visible STEP export.'

        bed_occ = component(root, '02 Bed platform | rotate Bed fold joint', (PX, PY, PZ))
        bed_occ.isGroundToParent = False
        bed = bed_occ.component
        door_start = (W - (4*DOOR_W + 3*DOOR_GAP))/2
        doors = []
        for i in range(4):
            name = f'5.{i+1} Door panel | 3/4 x 21-1/8 x 61-13/16'
            doors.append(dimensioned_box(bed, name, (door_start+i*(DOOR_W+DOOR_GAP), DOOR_Y, -0.5),
                                         (DOOR_W, DOOR_H, T), face, plywood))
            cutlist.append([name, 1, T, DOOR_W, DOOR_H, 'Rockler manual p6'])
            # Queen diagram p17: 10-3/8 from TOP to upper row, then 39-3/8 between rows.
            # Only each bracket's LOWER screw hole is dimensioned; transfer its other hole from the kit.
            centers = [
                (door_start+i*(DOOR_W+DOOR_GAP)+inset, DOOR_Y+DOOR_H-10.375-row, -0.5+T)
                for inset in (6, DOOR_W-6) for row in (0, 39.375)
            ]
            result['manufacturerPilotCuts'][f'Door {i+1} lower bracket holes — p17'] = drill_pilots(
                bed, doors[-1], f'Door {i+1} LOWER bracket pilots ONLY | Rockler p17',
                bed.xYConstructionPlane, -0.5+T, centers, 5/64, 5/8, (0, 0, -1))

        frame_occ = component(bed, 'Steel frame, 40 slats and retainers | REPRESENTATIVE')
        frame_occ.isGroundToParent = True
        hw = Hardware(frame_occ.component, black)
        frame_left, frame_right, rail, frame_z, frame_h = 1.5, W-1.5, 0.75, 0.25, 1.125
        for label, x in [('A1', frame_left), ('A2', frame_right-rail)]:
            hw.box(label + ' side frame bar', (x, FRAME_Y0, frame_z), (rail, FRAME_Y1-FRAME_Y0, frame_h))
        for label, y in [('E back', FRAME_Y0), ('E front', FRAME_Y1-rail)]:
            hw.box(label, (frame_left+rail, y, frame_z), (frame_right-frame_left-2*rail, rail, frame_h))
        middle_y = (FRAME_Y0 + FRAME_Y1)/2
        hw.box('D long center support', (frame_left+rail, middle_y-rail/2, frame_z),
               (frame_right-frame_left-2*rail, rail, frame_h))
        for i, x in enumerate([22, W/2, W-22]):
            for half, ya, yb in [('rear', FRAME_Y0+rail, middle_y-rail/2),
                                 ('front', middle_y+rail/2, FRAME_Y1-rail)]:
                hw.box(('C' if i == 1 else 'B') + f' {i} {half} support',
                       (x-rail/2, ya, frame_z), (rail, yb-ya, 0.65))
        for i in range(20):
            x = 3.15 + i*(80.45-2.3)/19
            for half, ya, yb in [('rear', FRAME_Y0+0.3, middle_y), ('front', middle_y, FRAME_Y1-0.3)]:
                # Three joined segments represent the shallow crown, not a supplier bending profile.
                length = yb-ya
                for segment in range(3):
                    crown = 0.09 if segment == 1 else 0.0
                    hw.box(f'O slat {i+1:02d} {half} section {segment+1}',
                           (x, ya+segment*length/3, 1.075+crown), (2.3, length/3, 0.30), slat_color)
            for label, y in [('P rear', FRAME_Y0+0.3), ('Q double', middle_y), ('P front', FRAME_Y1-0.9)]:
                hw.box(f'{label} cap {i+1:02d}', (x-0.1, y-0.3, 0.95), (2.5, 0.9, 0.4))
        for i, x in enumerate([door_start+DOOR_W/2, door_start+2.5*DOOR_W+2*DOOR_GAP]):
            y = DOOR_Y + DOOR_H*0.67
            hw.rod(f'Handle {i+1} grip', (x-3, y, -1.5), (x+3, y, -1.5), 0.1875)
            for end in [-3, 3]:
                hw.rod(f'Handle {i+1} standoff {end}', (x+end, y, -0.5), (x+end, y, -1.5), 0.1875)
        for i, x in enumerate([23, 63]):
            for dx in [-5, 5]:
                hw.rod(f'H{i+1} mattress retainer upright {dx}', (x+dx, -9.4, 1.375),
                       (x+dx, -9.4, 6.0), 0.13)
            hw.rod(f'H{i+1} mattress retainer crossbar', (x-5, -9.4, 6), (x+5, -9.4, 6), 0.13)
        hw.finish()

        mattress_occ = component(bed, '03 Queen mattress | 60 x 80 x 10 | toggle visibility')
        mattress_occ.isGroundToParent = True
        mattress = dimensioned_box(mattress_occ.component, 'Queen mattress envelope — verify actual weight',
                                   ((W-80)/2, -9, 1.5), (80, 60, 10), fabric)
        # Ground the mattress to the platform; nesting alone permits independent motion.
        leg_occ = component(bed, '04 Folding leg and foot bar | rotate Leg fold joint', (0, LEG_Y, LEG_Z))
        leg_occ.isGroundToParent = False
        legs = Hardware(leg_occ.component, black)
        for label, x in [('L', 1.85), ('R', W-2.60)]:
            legs.box(label + ' folding leg', (x, -0.45, -LEG_LENGTH), (0.75, 0.9, LEG_LENGTH))
            legs.box(label + ' floor foot', (x-0.25, -1.6, -LEG_LENGTH), (1.25, 3.2, 0.2))
        legs.box('N foot bar / folded mattress retainer', (2.6, -0.45, -LEG_LENGTH+0.6),
                 (W-5.2, 0.9, 0.75))
        legs.finish()
        # As-built joints need occurrence geometry in the owning component context.
        leg_sketch = bed.sketches.add(bed.xYConstructionPlane)
        leg_sketch.name = 'Leg fold axis | representative'
        leg_point = leg_sketch.sketchPoints.add(point(0, LEG_Y, LEG_Z))
        leg_geometry = adsk.fusion.JointGeometry.createByPoint(leg_point)
        leg_input = bed.asBuiltJoints.createInput(leg_occ, frame_occ, leg_geometry)
        leg_input.setAsRevoluteJointMotion(adsk.fusion.JointDirections.XAxisJointDirection)
        leg_joint = bed.asBuiltJoints.add(leg_input)
        leg_joint.name = 'Leg fold | 0 deg deployed / 180 deg retained'
        leg_joint.isLightBulbOn = False
        leg_sketch.isLightBulbOn = False
        bed_joint = revolute(root, cabinet_occ, bed_occ, 'Bed fold | 0 deg open / 90 deg closed — REPRESENTATIVE',
                             (PX, PY, PZ))

        # Fixed endpoint piston geometry is separate: NOT a simulated gas-spring mechanism.
        piston_poses = []
        for label, angle in [('OPEN', 0), ('CLOSED', math.pi/2)]:
            occ = component(root, 'Pistons '+label+' | endpoint representation, not dynamic simulation')
            occ.isGroundToParent = True
            piston = Hardware(occ.component, black)
            for side, x in [('L', PISTON_X_INSET), ('R', W-PISTON_X_INSET)]:
                a = (x, *PISTON_FIXED_YZ)
                ly, lz = PISTON_BED_YZ
                b = (x, PY+ly*math.cos(angle)-lz*math.sin(angle),
                     PZ+ly*math.sin(angle)+lz*math.cos(angle))
                span = math.dist(a, b)
                if not GAS_CYLINDER_LENGTH + GAS_ROD_LENGTH > span >= max(GAS_CYLINDER_LENGTH, GAS_ROD_LENGTH):
                    raise RuntimeError(f'Gas spring cannot span {span:.2f} in at {label}')
                unit = tuple((b[k]-a[k])/span for k in range(3))
                piston.rod(side+' gas cylinder', a,
                           tuple(a[k]+GAS_CYLINDER_LENGTH*unit[k] for k in range(3)), 0.43)
                piston.rod(side+' piston rod', b,
                           tuple(b[k]-GAS_ROD_LENGTH*unit[k] for k in range(3)), 0.19, silver)
            piston.finish()
            piston_poses.append(occ)
        piston_poses[1].isLightBulbOn = False
        adsk.doEvents()

        result['cabinetPartsInches'] = {b.name: verify_dimensions(b, s) for b, s in cabinet_bodies}
        result['doorPanelsInches'] = [verify_dimensions(b, (DOOR_W, DOOR_H, T)) for b in doors]
        result['mattressInchesXYZ'] = verify_dimensions(mattress, (80, 60, 10))
        result['cabinetExteriorInchesWHD'] = [W, H, D]
        result['cabinetClearOpeningInchesWHD'] = [W-2*T, H-2*T, D-T]
        result['minimumRequiredOpeningInchesWHD'] = [85.25, 62.125, 14.5]
        if not all(a >= b for a, b in zip(result['cabinetClearOpeningInchesWHD'],
                                          result['minimumRequiredOpeningInchesWHD'])):
            raise RuntimeError('Cabinet is smaller than Rockler minimum opening')
        result['motionScope'] = 'Endpoint placement only; no physical gas-spring, interference or load certification'
        result['sideCabinets'] = {
            side.lower(): build_side_cabinet(root, plywood, wood, natural, black, cutlist, side, origin_x)
            for side, origin_x in [('Left', W)]
        }
        result['combinedCarcassInchesWHD'] = [W+SIDE_W, H, D]
        result['cabinetFinish'] = {'color': '#182B49', 'material': plywood.name, 'nominalPlywoodThicknessInches': T}
        result['fusionVersion'] = app.version
        with (OUT / 'cabinet-cut-list.csv').open('w', newline='') as stream:
            writer = csv.writer(stream)
            writer.writerow(['Part', 'Quantity', 'Thickness_in', 'Width_in', 'Length_in', 'Source'])
            writer.writerows(cutlist)
        result['files'].append('cabinet-cut-list.csv')
        exporter = design.exportManager
        center_x = (W+SIDE_W)/2
        camera(app, (center_x, 0, H/2), (center_x, 180, H/2))
        if not app.activeViewport.setCurrentAsFront():
            raise RuntimeError('Could not define room-facing Front view')
        adsk.doEvents()
        result['frontView'] = {
            'lookDirection': list(app.activeViewport.frontEyeDirection.asArray()),
            'upDirection': list(app.activeViewport.frontUpDirection.asArray()),
        }
        for label, bed_angle, leg_angle in [('open', 0.0, 0.0), ('closed', math.pi/2, math.pi)]:
            leg_joint.jointMotion.rotationValue = leg_angle
            bed_joint.jointMotion.rotationValue = bed_angle
            piston_poses[0].isLightBulbOn = label == 'open'
            piston_poses[1].isLightBulbOn = label == 'closed'
            if design.snapshots.hasPendingSnapshot:
                design.snapshots.add()
            adsk.doEvents()
            mattress_context = next(o for o in root.allOccurrences
                                    if o.component == mattress_occ.component)
            mattress_world = mattress.createForAssemblyContext(mattress_context)
            expected_size = (80, 60, 10) if label == 'open' else (80, 10, 60)
            measured_size = verify_dimensions(mattress_world, expected_size)
            bounds = mattress_world.boundingBox
            measured_min = [getattr(bounds.minPoint, k) / IN for k in 'xyz']
            expected_min = ((W-80)/2, PY-9, PZ+1.5) if label == 'open' else ((W-80)/2, PY-11.5, PZ-9)
            if any(abs(a-b) > 0.0001 for a, b in zip(measured_min, expected_min)):
                raise RuntimeError(f'{label} mattress pose: expected {expected_min}, got {measured_min}')
            result.setdefault('verifiedPoses', {})[label] = {
                'mattressSizeInchesXYZ': measured_size,
                'mattressMinimumInchesXYZ': measured_min,
            }
            if label == 'open':
                leg_context = next(o for o in root.allOccurrences if o.component == leg_occ.component)
                foot_z = leg_context.preciseBoundingBox.minPoint.z / IN
                if abs(foot_z) > 0.0001:
                    raise RuntimeError(f'Deployed feet must meet z=0 floor; got {foot_z} inches')
                result['verifiedPoses'][label]['feetMinimumZInches'] = foot_z
            image = f'queen-horizontal-{label}.png'
            camera(app, (center_x, 25 if label == 'open' else 8, 29),
                   (center_x+105, 180, 135), image)
            result['files'].append(image)
            (OUT / 'media').mkdir(exist_ok=True)
            if not app.activeViewport.saveAsImageFile(
                    str(OUT / 'media' / f'ashleys-bed-{label}.png'), 2400, 1800):
                raise RuntimeError('Fusion media export failed: ' + label)
            if not app.activeViewport.setCurrentAsHome(True):
                raise RuntimeError('Could not save room-facing Home view')
            adsk.doEvents()
            filename = f'queen-horizontal-{label}.f3d'
            if not exporter.execute(exporter.createFusionArchiveExportOptions(str(OUT / filename))):
                raise RuntimeError('Fusion archive export failed: ' + filename)
            result['files'].append(filename)
            step = f'queen-horizontal-{label}.step'
            step_options = exporter.createSTEPExportOptions(str(OUT / step), root)
            step_options.isIncludingInvisibleBodies = False
            step_options.isIncludingInvisibleComponents = False
            if not exporter.execute(step_options):
                raise RuntimeError('STEP export failed: ' + step)
            result['files'].append(step)
            if label == 'open':
                mattress_occ.isLightBulbOn = False
                camera(app, (center_x, 25, 25), (center_x+95, 170, 145), 'queen-horizontal-frame.png')
                result['files'].append('queen-horizontal-frame.png')
                if not app.activeViewport.saveAsImageFile(
                        str(OUT / 'media' / 'ashleys-bed-frame.png'), 2400, 1800):
                    raise RuntimeError('Fusion frame media export failed')
                mattress_occ.isLightBulbOn = True
        drawing_bodies = []
        for occurrence in root.allOccurrences:
            for body in occurrence.component.bRepBodies:
                if body.material and body.material.name == plywood.name:
                    bounds = body.createForAssemblyContext(occurrence).boundingBox
                    drawing_bodies.append({
                        'name': body.name, 'owner': occurrence.name,
                        'min': [getattr(bounds.minPoint, axis) / IN for axis in 'xyz'],
                        'max': [getattr(bounds.maxPoint, axis) / IN for axis in 'xyz'],
                    })
        (OUT / 'drawing-geometry.json').write_text(json.dumps(
            {'units': 'inches', 'pose': 'closed', 'wood': drawing_bodies}, indent=2))
        result['status'] = 'exported; requires visual review of saved previews'
        result['timelineWarnings'] = [item.name for item in design.timeline
                                      if item.healthState != adsk.fusion.FeatureHealthStates.HealthyFeatureHealthState]
        status_file.write_text(json.dumps(result, indent=2))
        app.log('Murphy bed model exported to ' + str(OUT))
    except Exception:
        result['status'] = 'failed'
        result['error'] = traceback.format_exc()
        status_file.write_text(json.dumps(result, indent=2))
        adsk.core.Application.get().log(result['error'])
        raise
