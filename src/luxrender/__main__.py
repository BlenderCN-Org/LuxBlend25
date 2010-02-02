# -*- coding: utf8 -*-
#
# ***** BEGIN GPL LICENSE BLOCK *****
#
# --------------------------------------------------------------------------
# Blender 2.5 Exporter Framework - LuxRender Plug-in
# --------------------------------------------------------------------------
#
# Authors:
# Doug Hammond
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
# along with this program; if not, write to the Free Software Foundation,
# Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
#
# ***** END GPL LICENCE BLOCK *****
#
from ef.engine import engine_base

import ui.render_panels
import ui.materials

from ef.ef import ef

# Add standard Blender Interface elements
import properties_render
properties_render.RENDER_PT_render.COMPAT_ENGINES.add('luxrender')
properties_render.RENDER_PT_dimensions.COMPAT_ENGINES.add('luxrender')
properties_render.RENDER_PT_output.COMPAT_ENGINES.add('luxrender')
del properties_render

import properties_material
properties_material.MATERIAL_PT_context_material.COMPAT_ENGINES.add('luxrender')
del properties_material

from module import LuxManager as LM

# Then define all custom stuff
class luxrender(engine_base):
	bl_label = 'LuxRender'
	
	LuxManager = LM()
		
	interfaces = [
		ui.render_panels.engine,
		ui.render_panels.sampler,
		ui.render_panels.integrator,
		ui.render_panels.volume,
		ui.render_panels.filter,
		ui.render_panels.accelerator,
		
		ui.materials.material_editor
	]
	
	active = True
	
	def update_framebuffer(self, xres, yres, fb):
		'''
		this will be called by the LuxFilmDisplay thread started by LuxManager
		'''
		
		result = self.begin_result(0,0,xres,yres)
		lay = result.layers[0]
		# read default png file
		lay.load_from_file('luxout.png')
		self.end_result(result)
		
		
	
	def render(self, scene):
		self.LuxManager.reset()
		self.update_stats('', 'LuxRender: Parsing Scene')
		
		
		# THIS IS ALL JUST FOR TESTING BELOW;
		# In future use some classes to gather parameters into dicts for API calls please ;)
		l = self.LuxManager.lux_module
		matrix = scene.camera.matrix
		pos = matrix[3]
		forwards = -matrix[2]
		target = pos + forwards
		up = matrix[1]
		l.lookAt(pos[0], pos[1], pos[2], target[0], target[1], target[2], up[0], up[1], up[2])
		cs = {
			'fov': scene.camera.data.angle,
		}
		l.camera('perspective', list(cs.items()))
		
		fs = {
			# Set resolution
			'xresolution':   int(scene.render_data.resolution_x * scene.render_data.resolution_percentage / 100.0),
			'yresolution':   int(scene.render_data.resolution_y * scene.render_data.resolution_percentage / 100.0),
			
			# write only default png file
			'write_exr':         False,
			'write_png':         True,
			'write_tga':         False,
			'write_resume_flm':  False,
			'displayinterval':   5,
			'writeinterval':     8,
		}
		l.film('fleximage', list(fs.items()))
		l.worldBegin()
		
		es = {
			'sundir': (0,0,1)
		}
		l.lightSource('sunsky', list(es.items()))
		# DONE TESTING
		
		self.LuxManager.start(self)
		
		import time
		while self.LuxManager.started:
			time.sleep(1)
			self.update_stats('', 'LuxRender: Rendering | %s' % self.LuxManager.stats_thread.stats_string)
			if self.test_break():
				self.LuxManager.reset()
				self.update_stats('', '')
