var setVars = {

	"all": group_recent,
	"adipose": group_recent_adipose,
	"bone": group_recent_bone,
	"cells": group_recent_cells,
	"exosome": group_recent_evboost,
	"media": group_recent_media,
	"umbilical_cord": group_recent_umbilical_cord,
	"table_data": tablerecent_table,
	"filename": "2021-2022_PubsCitingRoosterBio",
	"tabname": "2021-2022"
};


//console.log("setVars = ")
//console.log(setVars)

var mapMakerRecent = mapMaker(setVars);
var tableMakerRecent = tableMaker(setVars);
