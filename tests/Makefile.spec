#!/usr/bin/env pbsmake
# This example turns a .IMG into a series of videos using blender/ffmpeg
#   .IMG -> .blend -> *.png -> .mp4

BLENDER_PATH?=/HiRISE/Users/$(id -u -n)/DTM_blender
RENDERED_PATH?=/HiRISE/Users/$(id -u -n)/DTM_blender_rendered
DTM_IMG_PATH?=/HiRISE/Data/DTM

# Defaults
FRAMES_PER_ORBIT?=288
KEEP_BLEND?=false
KEEP_FRAMES?=false
OUTPUT_DIR?=/HiRISE/Users/$(id -u -n)/DTM_blender_rendered

# Default frame rate if we are going to render a .blend
ANIM_FRAMERATE?=25

# Blender auto import script path
AUTO_IMPORT_SCRIPT?=/home/pirl/tims/Projects/blender/Scripts/auto_import_dtm.py

# This is not straight-forward to mess with currently
IMAGE_FORMAT="%04d.png"

## Default target to describe how to use this file
help::local_target:
	@echo Quick Usage/Examples:
	@echo '1)' say we have a released IMG file and we want to create orbits:
	@echo '  ' $DTM_IMG_PATH/.../DTEEC_006774_2020_007341_2020_A01.IMG
	@echo '  ' pbsmake orbits_DTEEC_006774_2020_007341_2020_A01
	@echo
	@echo '2)' say we have a .blend file and want to render it:
	@echo '  ' $BLENDER_PATH/DTEEC_006774_2020_007341_2020_A01-FlyAround.blend
	@echo '  ' pbsmake orbits_DTEEC_006774_2020_007341_2020_A01-FlyAround
	@echo
	@echo '3)' we want to create orbits for an unreleased .IMG file:
	@echo '  ' /path/to/DTEEC_000000_0000_000000_0000_A01.IMG
	@echo '  ' env BLENDER_PATH=/path/to/ pbsmake orbits_DTEEC_000000_0000_000000_0000_A01
	@echo

################################################################################
## Create a .blend from a .IMG
################################################################################
${BLENDER_PATH}/%.blend:
## Some defaults which should cover all conversion jobs (hopefully)
	#PBS -q blender
	#PBS -m a
	#PBS -l cput=00:30:00
	#PBS -l walltime=1:00:00
	#PBS -l mem=4g
	#PBS -k o
	#PBS -j oe
	#PBS -V
	#PBS -S /bin/bash
	set -o nounset
	set -o errexit

	if [[ -z "$DTM_IMG" ]]; then
	  DTM_IMG=$(find $DTM_IMG_PATH -name ${pm_target_match}*.IMG | tail -1)
	  [[ -z "$DTM_IMG" ]] && {
	    echo could not find ${pm_target_match}*.IMG in $DTM_IMG_PATH 1>&2
	    exit -1
	  }
	fi

	# Where is the actual file?
	DTM_IMG_REAL=$(readlink $DTM_IMG 2> /dev/null)
	[[ ! -z "$DTM_IMG_REAL" ]] && DTM_IMG=$DTM_IMG_REAL

	# Attempt to find a texture if none is specified
	if [[ -z "$DTM_TEXTURE" ]] && [[ -z "$SKIP_IMG2blend" ]]; then

	  # Attempt to locate the EXTRAS directory for the specified DTM. If this is
	  # already set then it will simply use the supplied env for DTM_EXTRAS_DIR
	  if [[ -z "$DTM_EXTRAS_DIR" ]]; then
	    DTM_EXTRAS_DIR=$(dirname $DTM_IMG)
	    DTM_EXTRAS_DIR=${DTM_EXTRAS_DIR//DTM/EXTRAS\/DTM}
	    # Sometimes EXTRAS is actually Extras
	    [[ -x "$DTM_EXTRAS_DIR/" ]] || DTM_EXTRAS_DIR=${DTM_EXTRAS_DIR//EXTRAS/Extras}
	  fi

	  # We need an EXTRAS dir in order to find an image to drape over the DTM
	  [[ -x $DTM_EXTRAS_DIR/ ]] || die could not find EXTRAS directory for DTM: $DTM_EXTRAS_DIR

	  # Preference for what to drape over an image
	  for EXTRAS_TYPE in cb sb br; do
	    if [[ ! -r "${DTM_TEXTURE}" ]]; then
	      export DTM_TEXTURE=$(find "$DTM_EXTRAS_DIR" -name \*.${EXTRAS_TYPE}.jpg | tail -1)
	    fi
	  done

	fi

	DTM_TEXTURE_RL=$(readlink "$DTM_TEXTURE")
	[[ ! -z "$DTM_TEXTURE_RL" ]] && DTM_TEXTURE="$DTM_TEXTURE_RL"

	# We need a texture if we are creating a .blend file
	if [[ ! -r "${DTM_TEXTURE}" ]]; then
	  die could not find valid .jpg image to drape on DTM: ${DTM_TEXTURE}
	fi

	echo '    IMG:' $DTM_IMG
	echo 'TEXTURE:' $DTM_TEXTURE
	echo '  BLEND:' /tmp/${pm_target_match}.blend :: ${BLENDER_PATH}/${pm_target_match}.blend
	mkdir -p "$BLENDER_PATH"
	DTM_BLEND=/tmp/${pm_target_match}.blend blender -b -P /home/pirl/tims/Projects/blender/Scripts/auto_import_dtm.py -noaudio
	mv -f /tmp/${pm_target_match}.blend ${BLENDER_PATH}/

################################################################################
## Render a .blend into a sequence of frames
################################################################################
${RENDERED_PATH}/%/frames/: ${BLENDER_PATH}/${pm_target_match}.blend
	#PBS -q blender
	#PBS -m a
	#PBS -l cput=48:00:00
	#PBS -l walltime=4:00:00
	#PBS -l mem=12g
	#PBS -l ncpus=8
	#PBS -k o
	#PBS -j oe
	#PBS -V
	#PBS -S /bin/bash
	WORKING_DIR=/tmp/$PBS_JOBID
	BLEND=$WORKING_DIR/${pm_target_match}.blend
	IMAGES="$WORKING_DIR/"
	mkdir -p "$WORKING_DIR"
	cd "$WORKING_DIR"
	cp -f "$BLENDER_PATH/"${pm_target_match}.blend $BLEND
	time blender -t 8 -b "$BLEND" -F PNG --render-output "$IMAGES####.png" -x 1 -a
	mv -f "$IMAGES"*.png "${pm_target_name}"
	cd /
	rm -rf "\$WORKING_DIR"

################################################################################
## Compile frames into various movie formats
################################################################################
${RENDERED_PATH}/%-1080.mp4: ${RENDERED_PATH}/${pm_target_match}/frames/
	#PBS -q blender
	#PBS -m a
	#PBS -l cput=00:05:00
	#PBS -l walltime=00:10:00
	#PBS -l mem=1g
	#PBS -k o
	#PBS -j oe
	#PBS -V
	mkdir -p "$OUTPUT_DIR" 2> /dev/null
	time ffmpeg -loglevel fatal -r $ANIM_FRAMERATE -i "$RENDERED_PATH/${pm_target_match}/frames/$IMAGE_FORMAT" -s hd1080 -b 8000k -y ${pm_target_name}

${RENDERED_PATH}/%-720.mp4: ${RENDERED_PATH}/frames/${pm_target_match}
	#PBS -q blender
	#PBS -m a
	#PBS -l cput=00:05:00
	#PBS -l walltime=00:10:00
	#PBS -l mem=1g
	#PBS -k o
	#PBS -j oe
	#PBS -V
	mkdir -p "$OUTPUT_DIR" 2> /dev/null
	time ffmpeg -loglevel fatal -r $ANIM_FRAMERATE -i "$RENDERED_PATH/frames/$IMAGE_FORMAT" -s hd720 -b 4000k -y ${pm_target_name}

${RENDERED_PATH}/%-480.mp4: ${RENDERED_PATH}/frames/${pm_target_match}
	#PBS -q blender
	#PBS -m a
	#PBS -l cput=00:05:00
	#PBS -l walltime=00:10:00
	#PBS -l mem=1g
	#PBS -k o
	#PBS -j oe
	#PBS -V
	mkdir -p "$OUTPUT_DIR" 2> /dev/null
	time ffmpeg -loglevel fatal -r $ANIM_FRAMERATE -i "$RENDERED_PATH/frames/$IMAGE_FORMAT" -s hd480 -b 1000k -y ${pm_target_name}

################################################################################
## Cleanup once other jobs are done...
################################################################################
# afterany:jobid[:jobid...]
#   This job may be scheduled for execution after jobs jobid have terminated, with or without errors.
orbits_%::afterany: ${RENDERED_PATH}/${pm_target_match}-480.mp4
orbits_%::afterany: ${RENDERED_PATH}/${pm_target_match}-720.mp4
orbits_%::afterany: ${RENDERED_PATH}/${pm_target_match}-1080.mp4
	#PBS -q blender
	#PBS -m ae
	#PBS -k o
	#PBS -j oe
	#PBS -l cput=00:05:00
	#PBS -l walltime=00:10:00
	#PBS -l mem=128m
	#PBS -S /bin/bash
	@echo all dependencies rendered ... cleaning up
	if [[ "$KEEP_FRAMES" == 'false' ]]; then
	  rm -f $RENDERED_PATH/frames/*.png
	  rmdir $RENDERED_PATH/frames 2> /dev/null || true
	fi
	[[ "$KEEP_BLEND" == "false" ]] && rm -f ${BLENDER_PATH}/${pm_target_match}.blend || true
	touch ${pm_target_match}

