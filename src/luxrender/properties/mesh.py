# -*- coding: utf8 -*-
#
# ***** BEGIN GPL LICENSE BLOCK *****
#
# --------------------------------------------------------------------------
# Blender 2.5 LuxRender Add-On
# --------------------------------------------------------------------------
#
# Authors:
# Doug Hammond, Daniel Genrich
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, see <http://www.gnu.org/licenses/>.
#
# ***** END GPL LICENCE BLOCK *****
#
from extensions_framework import declarative_property_group
from extensions_framework.validate import Logic_Operator as LO

from .. import LuxRenderAddon
from ..export import ParamSet
from ..properties.material import texture_append_visibility
from ..properties.texture import FloatTextureParameter
from ..util import dict_merge

class MeshFloatTextureParameter(FloatTextureParameter):
	def texture_slot_set_attr(self):
		# Looks in a different location than other FloatTextureParameters
		return lambda s,c: c.luxrender_mesh

TF_displacementmap = MeshFloatTextureParameter(
	'dm',
	'Displacement Map',
	real_attr='displacementmap',
	add_float_value=False
)

@LuxRenderAddon.addon_register_class
class luxrender_mesh(declarative_property_group):
	'''
	Storage class for LuxRender Camera settings.
	'''
	
	ef_attach_to = ['Mesh', 'SurfaceCurve', 'TextCurve', 'Curve']
	
	controls = [
		'mesh_type',
		['portal', 'AR_enabled'],
		['projection', 'ccam'],
		'ucam',
		['subdiv','sublevels'],
		['nsmooth', 'sharpbound'],
	] + \
		TF_displacementmap.controls + \
	[
		['dmscale', 'dmoffset']
	]
	
	visibility = dict_merge({
		'ccam':		{'projection': True },
		'ucam': 	{'projection': True , 'ccam': False },
		'nsmooth':		{ 'subdiv': LO({'!=': 'None'}) },
		'sharpbound':	{ 'subdiv': LO({'!=': 'None'}) },
		'sublevels':	{ 'subdiv': LO({'!=': 'None'}) },
		'dmscale':		{ 'subdiv': LO({'!=': 'None'}), 'dm_floattexturename': LO({'!=': ''}) },
		'dmoffset':		{ 'subdiv': LO({'!=': 'None'}), 'dm_floattexturename': LO({'!=': ''}) },
	}, TF_displacementmap.visibility )
	
	visibility = texture_append_visibility(visibility, TF_displacementmap, { 'subdiv': LO({'!=': 'None'}) })
	
	properties = [
		{
			'type': 'enum',
			'attr': 'mesh_type',
			'name': 'Export as',
			'items': [
				('global', 'Use default setting', 'global'),
				('native', 'LuxRender mesh', 'native'),
				('binary_ply', 'Binary PLY', 'binary_ply')
			],
			'default': 'global'
		},
		{
			'type': 'bool',
			'attr': 'portal',
			'name': 'Exit Portal',
			'default': False,
		},
		{
			'type': 'enum',
			'attr': 'subdiv',
			'name': 'Subdivision Scheme',
			'default': 'None',
			'items': [
				('None', 'None', 'None'),
				('loop', 'loop', 'loop'),
				('microdisplacement', 'microdisplacement', 'microdisplacement')
			]
		},
		{
			'type': 'bool',
			'attr': 'nsmooth',
			'name': 'Normal smoothing',
			'default': True,
		},
		{
			'type': 'bool',
			'attr': 'sharpbound',
			'name': 'Sharpen Bounds',
			'default': False,
		},
		{
			'type': 'int',
			'attr': 'sublevels',
			'name': 'Subdivision Levels',
			'default': 2,
			'min': 0,
			'soft_min': 0,
			'max': 1000,
			'soft_max': 1000
		},
		{ 
			'type': 'bool',
			'attr': 'AR_enabled',
			'name': 'Is an AR surface',
			'description': 'Using for declare the object as support object in Augmented Reality Scene',
			'default': False,
		},
		{
			'type': 'bool',
			'attr': 'projection',
			'name': 'Use projector texture',
			'description': 'Select the projector texture type for the object',
			'default': False,
		},
		{
			'type': 'bool',
			'attr': 'ccam',
			'name': 'Projection point at current Camera',
			'description': 'Select the position of current camera as the projection point for texture',
			'default': False,
		},
		{
			'type': 'float_vector',
			'attr': 'ucam',
			'name': 'Define Projection point',
			'description': 'Define the projection point for texture',
			'default': (0.0, 0.0, 0.0),
			'save_in_preset': True,
		},
	] + \
		TF_displacementmap.properties + \
	[
		{
			'type': 'float',
			'attr': 'dmscale',
			'name': 'Scale',
			'description': 'Displacement Map Scale',
			'default': 1.0,
			'precision': 6,
		},
		{
			'type': 'float',
			'attr': 'dmoffset',
			'name': 'Offset',
			'description': 'Displacement Map Offset',
			'default': 0.0,
			'precision': 6,
		},
	]
	

	def get_shape_IsSupport(self):
		return self.AR_enabled
	
	def get_paramset(self, scene):

		params = ParamSet()
		
		# check if subdivision is used
		if self.subdiv != 'None':
			params.add_string('subdivscheme', self.subdiv)
			params.add_integer('nsubdivlevels',self.sublevels)
			params.add_bool('dmnormalsmooth', self.nsmooth)
			params.add_bool('dmsharpboundary', self.sharpbound)
			
		
		export_dm = TF_displacementmap.get_paramset(self)
		
		if self.dm_floattexturename != '' and len(export_dm) > 0:
			params.add_string('displacementmap', self.dm_floattexturename)
			params.add_float('dmscale', self.dmscale)
			params.add_float('dmoffset', self.dmoffset)

		if self.AR_enabled:
			params.add_bool('support', self.AR_enabled)
		if self.projection:
			params.add_bool('projection', self.projection)
			if self.ccam:
				cam_pos =  scene.camera.data.luxrender_camera.lookAt(scene.camera)
				params.add_point('cam', ( cam_pos[0], cam_pos[1], cam_pos[2] ) )
			else:
				params.add_point('cam', self.ucam)
		
		return params
