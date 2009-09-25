# coding=utf-8

"""
Generates a matlab file that would create the arboris-matlab equivalent to
an arboris-python robot.
"""
__author__ = ("Joseph SALINI <joseph.salini@gmail.com>",
              "Sébastien BARTHÉLEMY <sebastien.barthelemy@gmail.com>")

from arboris.core import Body, SubFrame, Joint, World
from arboris import joints, shapes
from numpy import zeros, eye


class GenerationError(RuntimeError):
    pass

class ConversionError(RuntimeError):
    pass

class MatlabConverter(object):
    """Convert an arboris-python joint to another one that is compatible with arboris-matlab.
    
    This works around two caveats of arboris-python:
    
    - the first joint should always be a FreeJoint
    
    - the other joints can only have one rotational dof.
    
    # TODO: we should handle gpos and gvel
    
    **Examples:**
        
        >>> from arboris.robots.human36 import add_human36
        >>> w = World()
        >>> add_human36(w)
        >>> MatlabConverter().convert_robot(w, w.getjoints()[0])
    
        >>> from arboris.robots.simplearm import add_simplearm
        >>> w = World()
        >>> add_simplearm(w)
        >>> MatlabConverter().convert_robot(w, w.getjoints()[0])

    """
    
    def __init__(self):
        # default taken from arboris-matlab human36:
        self.small_mass = 1.0e-2
        # defaults taken from arboris-matlab's t06_ConstructionRobot.m:
        self.base_mass = 1.0e4
        self.base_lengths = [0.5/2, 0.5/5, 0.5/10]
        self.contact_radius = 0.05
        self.friction_coeff = 0.05
        
    def convert_root_joint(self, world, root_joint):
        assert isinstance(root_joint, Joint)
        assert isinstance(world, World)
        assert root_joint.frames[0].body is world.ground 
        if isinstance(root_joint, joints.FreeJoint):
            # nothing to do
            pass
        else:
            from arboris.homogeneousmatrix import transl
            from arboris.massmatrix import box as boxmass
            from arboris.shapes import Box, Sphere
            from arboris.constraints import SoftFingerContact
            # add a "free-floating" base body to the robot
            base = Body(mass=boxmass(self.base_lengths, self.base_mass))
            world.replace_joint(root_joint, 
                                root_joint.frames[0], 
                                joints.FreeJoint(), 
                                base,
                                base,
                                root_joint, 
                                root_joint.frames[1])
            # add a ground plane
            r = self.contact_radius
            ground_lengths = [ d+4*r for d in self.base_lengths]
            ground_plane = Box(world.ground, ground_lengths)
            world.register(ground_plane)
            # put 4 spheres at the bottom of the base
            (x, y, z) = self.base_lengths
            for (i, j) in ((1, 1), (1, -1), (-1, -1), (-1, 1)):
                sf = SubFrame(base, transl(i*x/2, -y/2, j*z/2))
                sh = Sphere(sf, r)
                world.register(sh)
                contact = SoftFingerContact((ground_plane, sh), self.friction_coeff)
                world.register(contact)
                
                
    def convert_robot(self, world, root_joint):
        child_body = root_joint.frames[1].body
        self.convert_root_joint(world, root_joint)
        self._traverse(world, child_body)
        
    def _traverse(self, world, body):
        """Recurse through the tree."""
        assert isinstance(world, World)
        assert isinstance(body, Body)
        for joint in body.childrenjoints:
            child_body = joint.frames[1].body
            # try a conversion:
            self.convert_nonroot_joint(world, joint)
            # recurse:
            self._traverse(world, child_body)         

    
    def convert_nonroot_joint(self, world, joint):
        """Convert a joint, which is assume not to be the root one of the robot."""
        assert isinstance(joint, Joint)
        assert isinstance(world, World)
        assert joint.frames[0].body is not world.ground 
        frame0, frame1 = joint.frames
        
        def name(suffix):
            if joint.name is None:
                return None
            else:
                return joint.name+suffix
                        
        def mass():
            from numpy import diag
            return self.base_mass*diag([1.0, 1.0, 1.0, 0.1, 0.1, 0.1])
        
        if isinstance(joint, joints.RzJoint) or \
            isinstance(joint, joints.RyJoint) or \
            isinstance(joint, joints.RxJoint):
                # nothing to do, the joint is compatible
                pass
        elif isinstance(joint, joints.RzRyRxJoint):
            Rz = joints.RzJoint(name=name('Rz'))
            Bzy = Body(mass=mass())
            Ry = joints.RyJoint(name=name('Ry'))
            Byx = Body(mass=mass())
            Rx = joints.RxJoint(name=name('Rx'))
            world.replace_joint(joint, frame0, Rz, Bzy, Bzy, Ry, Byx, Byx, Rx, frame1)

        elif isinstance(joint, joints.RzRyJoint):
            Rz = joints.RzJoint(name=name('Rz'))
            Bzy = Body(mass=mass())
            Ry = joints.RyJoint(name=name('Ry'))
            world.replace_joint(joint, frame0, Rz, Bzy, Bzy, Ry, frame1)

        elif isinstance(joint, joints.RyRxJoint):
            Ry = joints.RyJoint(name=name('Ry'))
            Byx = Body(mass=mass())
            Rx = joints.RxJoint(name=name('Rx'))
            world.replace_joint(joint, frame0, Ry, Byx, Byx, Rx, frame1)

        elif isinstance(joint, joints.RzRxJoint):
            Rz = joints.RzJoint(name=name('Rz'))
            Bzx = Body(mass=mass())
            Rx = joints.RxJoint(name=name('Rx'))
            world.replace_joint(joint, frame0, Rz, Bzx, Bzx, Rx, frame1)


class  MatlabGenerator(object):
    """Generates a matlab file that would create the arboris-matlab equivalent to an arboris-python robot.

    **Tests:**
    
    >>> from arboris.core import simplearm
    >>> import cStringIO
    >>> w = simplearm()
    >>> from arboris.robots.human36 import add_human36
    >>> add_human36(w)
    >>> mc = MatlabGenerator(w)
    >>> stream = cStringIO.StringIO()
    >>> #stream = open(filename, "w")
    >>> mc.make_robot(w.ground.childrenjoints[0], stream, 'simplearm')
    Traceback (most recent call last):
        ...
    GenerationError: The root joint must be a FreeJoint.
    >>> mc.make_robot(w.ground.childrenjoints[1], stream, 'human36')
    Traceback (most recent call last):
        ...
    GenerationError: Cannot generate joints of type "<class 'arboris.joints.RzRyRxJoint'>".
    >>> stream.close()

    The tests uses ``cStringIO.StringIO()`` instead of ``open()`` in 
    order to avoid cluttering the filesystem, but the expected usage is 
    to write in files.
    
    """

    def __init__(self, world):
        self.w = world
        self._b_map = {}
    
    def make_robot(self, root_joint, stream, name=None):
        assert isinstance(root_joint, Joint)
        if not isinstance(root_joint, joints.FreeJoint):
            raise GenerationError("The root joint must be a FreeJoint.")
        self.stream = stream
        try:
            self._add_tree(name)
            self._add_branch(1)
            self._traverse( [root_joint], 1, 1 )
            self.add_shapes()
            self.close_stream()
        except:
            self.stream.write(
                "\n!!! SOMETHING WENT MAD: do not use this file !!!\n")
            raise

    def _add_tree(self, name):
        """Add the headings for a new (empty) tree."""
        
        text = """
% This file was auto-generated by arboris-python

function robot = create_{name}()
%Returns a robot, named {name}.

% create a tree struct that will be later converted
tree.name = '{name}';
""".format(name=name) #TODO: we should ensure name is a valid matlab function name (no -,+...)
        self.stream.write(text) 
    
    def _finish(self):
        text="""
robot = arb_robot(arb_treestructtree(tree));
"""
        self.stream.write(text)

    
    def _add_branch(self, num_br, parent=(0,0) ):
        """Add the headings for a new (empty) branch."""
    
        text = """
%% Create branch {br}:
tree.br({br}).name = 'branch {br}';
tree.br({br}).root_jk={par};
""".format(br=num_br, par="{"+str(parent[0])+" "+str(parent[1])+"}")
        self.stream.write(text) 
        
    
    def _add_link(self, joint, num_br, num_bd):
        """Add a link (a joint and its child body)."""
        
        H00L1 = joint.frames[0].bpose
        H11L0 = joint.frames[1].bpose
        body = joint.frames[1].body
        self._b_map[body.name] = (num_br, num_bd)
        if isinstance(joint, joints.RxJoint):
            jtype = "[0 0 0 1 0 0]"
        elif isinstance(joint, joints.RyJoint):
            jtype = "[0 0 0 0 1 0]"
        elif isinstance(joint, joints.RzJoint):
            jtype = "[0 0 0 0 0 1]"
        elif isinstance(joint, joints.FreeJoint):
            if num_br != 1 or num_bd != 1:
                raise GenerationError(
                    'FreeJoint is only available as the root joint.')
            jtype = "eye(6)"
        else:
            raise GenerationError(
                'Cannot generate joints of type "{0}".'.format(type(joint)))
        text = """
tree.br({br}).bd({bd}).name = '{name}'; % body name is '{name2}'
tree.br({br}).bd({bd}).E = {jtype}';
tree.br({br}).bd({bd}).H_0_0L1 = ...
{H0};
tree.br({br}).bd({bd}).H_1_1L0 = ...
{H1};
tree.br({br}).bd({bd}).M = ...
{mass};
tree.br({br}).bd({bd}).shape(1).type = 'sphere';
tree.br({br}).bd({bd}).shape(1).dims = [0.01];
tree.br({br}).bd({bd}).shape(1).H = eye(4);
""".format(
        br=num_br,
        bd=num_bd,
        name=joint.name,
        name2=body.name,
        mass=_flip(body.mass),
        jtype=jtype,
        H0 = H00L1,
        H1 = H11L0
        )
        self.stream.write(text)
       
        
    def _add_shapes(self):
        """Add the shapes for all the links."""
        
        self.stream.write("\n\n% Write the registered contacting shapes\n")
        num_in_bd = {}
        shapes = self.w.getshapes()
        for v in shapes:
            body = v.frame.body
            (br,bd)= self._b_map[body.name]
            if body.name in num_in_bd.iterkeys():
                num_in_bd[body.name] += 1
            else:
                num_in_bd[body.name] = 2
            if isinstance(v, shapes.Point):
                stype='sphere'
                dims='[0.01]'
            Hpose=v.frame.bpose
            text="""
tree.br({br}).bd({bd}).shape({num}).type = '{stype}';
tree.br({br}).bd({bd}).shape({num}).dims = {dims};
tree.br({br}).bd({bd}).shape({num}).H = {H};
tree.br({br}).bd({bd}).shape({num}).gr_props = {visu};
""".format(
                br=br,
                bd=bd,
                num=num_in_bd[body.name],
                stype=stype,
                dims=dims,
                H=Hpose,
                visu="{'FaceColor','Visible'; [1 0 0] ,'on'}")
            self.stream.write(text)
        
    
    def _traverse(self, joints, br, bd):
        """Recurse through the tree."""
        parent = (br, bd-1)
        if len(joints) == 0:
            # we are at the end of a branch
            return br
        else:
            j = joints[0]
            self._add_link(j, br, bd)
            bd += 1
            br = self._traverse(j.frames[1].body.childrenjoints, br, bd)
            for j in joints[1:]:
                br+=1
                self._add_branch(br, parent)
                self._add_link(j, br, 1)
                br = self._traverse(j.frames[1].body.childrenjoints, br, 2)
            return br


def _flip(m):
    """Flip anti-diagonal blocks of an array."""
    assert m.shape == (6, 6)
    fm = zeros((6,6))
    fm[0:3,0:3] = m[3:6,3:6]
    fm[3:6,3:6] = m[0:3,0:3]
    fm[0:3,3:6] = m[3:6,0:3]
    fm[3:6,0:3] = m[0:3,3:6]
    return fm

