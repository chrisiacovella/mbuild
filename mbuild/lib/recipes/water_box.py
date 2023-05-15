import numpy as np
import math as math
from warnings import warn

from mbuild import Box, Compound, clone, force_overlap, load
from mbuild.exceptions import MBuildError

import mbuild.lib.molecules.water as water_models

__all__ = ["WaterBox"]

class WaterBox(Compound):
    """Generate a box of 3-site water molecules.
    
    Efficiently create an mbuild Compound containing water at density ~1000 kg/m^3
    where local molecule orientations should exist in relatively low energy states.
    This loads in a configuration previously generated with packmol and relaxed with
    GROMACS via NVT simulation at 305K using tip3p model, simulated in a 4 nm^3 box.
    The code will duplicate/truncate the configuration as necessary to satisify the
    given box dimensions.
    
    Parameters
    ----------
    box : mb.Box
        The desired box to fill with water
    edge: float or list of floats, default=0.1 nm
        Specifies the gutter around the system to avoid overlaps at boundaries
    model: mb.Compound, optional, default=water_models.WaterTIP3P()
        The specified 3-site water model to be used. This uses the force overlap
        command to translate and orient the specified water model to the given coordinates.
        See mbuild/lib/molecules/water.py for available water models or extend the base model.
    mask: mb.Compound, optional, default=None
        Remove water molecules from the final configuration that overlap with the Compound
        specified by the mask. If the element field is set, the sum of the particle radii
        will be used.
    r_cut: float, optional, default=0.15 nm
        If the element is not set for a Compound (in either the water model or the mask),
        the r_cut value will be used for the radii.
    radii_padding: float, optional, default=0.0 nm
        A padding value added to the radii for the masking. This can be used to allow more (or less if negative)
        space between the mask and the water.
        
        
    """
    def __init__(self, box, edge = 0.1, model = water_models.WaterTIP3P(), mask=None, r_cut = 0.15, radii_padding=0.0):

        super(WaterBox, self).__init__()
        
        # check if we are given a list or single value
        if isinstance(edge, list):
            assert(len(edge) == 3)
            edges = np.array(edge)
        else:
            edges = np.array([edge,edge,edge])

        # If a model is specified, we will check to ensure that
        # the first particle in the compound corresponds to Oxygen.
        
        if model is not None:
            assert isinstance(model, Compound)
            particles = [p for p in model.particles()]
            if 'O' not in particles[0].name:
                raise MBuildError('The first particle in model needs to correspond to oxygen')
 
        # check if mask is set
         if mask is not None:
            if not isinstance(mask, list):
                assert isinstance(mask, mb.Compound)
            elif isinstance(mask, list):
                # in case we are specified a list of Compounds,
                # we will make sure it is a 1d list.
                mask = [e for e in self._flatten_list(mask)]
                for entry in mask:
                    assert isinstance(entry, mb.Compound)
                    
        # read in our propotype, a 4.0x4.0x4.0 nm box
        # our prototype was relaxed in GROMACs at 305 K, density 1000 kg/m^3 using tip3p
        aa_waters = load('water_proto.gro')

        # loop over each water in our configuration
        # add in the necessary bonds missing from the .gro file
        # rename particles/Compound according to the given water model
        for water in aa_waters.children:
           
            water.add_bond((water.children[0], water.children[1]))
            water.add_bond((water.children[0], water.children[2]))
                
            temp = clone(model)
            force_overlap(temp, temp, water, add_bond=False)
            water.name=model.name
            water.children[0].name = model.children[0].name
            water.children[1].name = model.children[1].name
            water.children[2].name = model.children[2].name
            water.xyz = temp.xyz
          
        # scaling parameters for the new box
        scale_Lx = math.ceil(box.Lx/aa_waters.box.Lx)
        scale_Ly = math.ceil(box.Ly/aa_waters.box.Ly)
        scale_Lz = math.ceil(box.Lz/aa_waters.box.Lz)
        
        water_system_list = []
        
        # we will create a list of particles for the mask
        # if specified now to save time later
        if mask is not None:
            if isinstance(mask, mb.Compound):
                p_mask = [ p for p in mask.particles()]
            else:
                p_mask = []
                for entry in mask:
                    p_mask =  p_mask + [ p for p in mask.particles()]
                    
        # add water molecules to a list
        # note we add to a list first, as this is more efficient than calling
        # the Compound.add function repeatedly as the Compound size grows.
        for water in aa_waters.children:
            for i in range(0,scale_Lx):
                for j in range(0,scale_Ly):
                    for k in range(0,scale_Lz):
                        shift = np.array([i*aa_waters.box.Lx, j*aa_waters.box.Ly, k*aa_waters.box.Lz])
                        if mask is not None:
                            particles = [p for p in water.particles()]
                            status = True
                            
                            # note this could be sped up using a cell list
                            # will have to wait until that PR is merged
                            for p1 in particles:
                                for p2 in p_mask:
                                    dist= np.linalg.norm(p1.pos-p2.pos)
                                     
                                    if p1.element is None:
                                        c1 = cut/2.0
                                    else:
                                        c1 = p1.element.radius_alvarez/10.0+radii_padding
                                    if p2.element is None:
                                        c2 = cut/2.0
                                    else:
                                        c2 = p2.element.radius_alvarez/10.0+radii_padding
                                    cut_value = c1+c2
                                    if dist <= cut_value:
                                        status = False
                            if status:
                                temp = mb.clone(water)
                                temp.translate(shift)
                                water_system_list.append(temp)
                        else:

                            temp = mb.clone(water)
                            temp.translate(shift)
                            water_system_list.append(temp)
        
            
        # add to the Compound and set box size
        self.add(water_system_list)
        self.box = box
