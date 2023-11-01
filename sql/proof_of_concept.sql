-- 'Single Slide Multiple Choice No Answer Bank'
-- 'Single Slide Multiple Choice With Answer Bank'
-- 'Multi Slide With Answer Bank'
-- 'Multi Slide No Answer Bank'
-- 'Single Slide Open Ended'
-- 'Single Slide Media'

drop table if exists questions;
drop table if exists single_slide_multiple_choice_no_answer_bank;

create table questions (
	id SERIAL primary key,
	title varchar,
	question_type varchar,
	category varchar,
	game_id varchar default '052023',
	has_been_used bool default true,
	question_number integer

);

insert into questions (question_type, title, question_number, category)
values 
	('Single Slide Multiple Choice No Answer Bank', 'For each of the following sports franchises, name a city that the franchise was previoulsy located in (1 Point Each)', 1, 'Sports Franchises'),
	('Single Slide Open Ended', 'Can you name all of the current Supreme Court justices (1 Point for Each Correct Answer, -1 Point for Each Incorrect Answer)', 2, 'Justice'),
	('Single Slide Multiple Choice No Answer Bank', 'Identify the punctuation mark that shares a key on a computer keyboard with each of the following numbers (1 Point Each)', 3, 'Computers'),
	('Single Slide Multiple Choice With Answer Bank', 'Match the coffee drink to the description (1 Point Each)', 4, 'Coffee'),
	('Single Slide Multiple Choice No Answer Bank', 'Identify what has a greater land area (1 Point Each)', 5, 'Land'),
	('Single Slide Multiple Choice With Answer Bank', 'Match the dying words of the famous person to the famous person (1 Point Each)', 6, 'Words'),
	('Single Slide Multiple Choice No Answer Bank', 'For each of the following pairs of historical figures, were they alive at the same time? (1 Point Each)', 7, 'Lifetimes'),
	('Single Slide Multiple Choice With Answer Bank', 'Match each of the following phobias to the description of the phobia (1 Point Each)', 8, 'Fear'),
	('Multi Slide With Answer Bank', 'You will be shown a picture of a city from each of the following regions: Central America, The Middle East, Central Asia (The Stans), Sub-Saharan Africa. Each city shown is the city with the largest population of any city in that region. For 1 point, match the picture of a city to the region. For 2 points, name the country for which the city is located. For 3 points, name the city shown in the image. (24 Points Possible)', 9, 'Cities'),
	('Single Slide Multiple Choice No Answer Bank', 'For each of the following unlabeled countries, you will be given the population in a specific year, and the average annual population growth rate between that year and a later year. Estimate the population in the outer year (2 Point Each)', 10, 'Growth'),
	('Single Slide Multiple Choice No Answer Bank', 'Rank the following companies, from highest to lowest 2022 revenues. (1 Point Each)', 11, 'Business'),
	('Single Slide Multiple Choice No Answer Bank', 'Rank the following companies, from highest to lowest 2022 revenues. (1 Point Each)', 12, 'Business'),
	('Single Slide Multiple Choice No Answer Bank', 'Based on the clue identify the person/character/thing/etc. The last name in the answer for question A will be the first name in the answer for question B, and so on. (2 Points Each)', 13, 'First Name Last Name'),
	('Multi Slide No Answer Bank', 'You will be shown the poster for four films. For each of these films, the director of the film also directed a film that won the Oscar for Best Picture between 2010-2023. Name the film that won Best Picture for 2 Points, and name the director for 3 points (5 Points Each).', 14, 'Movies'),
	('Single Slide Media', 'Identify the Studio/Production company by their iconic sound (2 Points Each).', 15, 'Movies'),
	('Single Slide Media', 'Identify the data being shown on the map (5 Points)', 16, 'Guess The Data'),
	('Single Slide Media', 'Identify the place from the aerial photograph (5 Points)', 17, 'Birds Eye View'),
	('Single Slide Media', 'Each of the four images is a visual punn. All four of the images represent something that belong to the same category. Identify each image and the category (2 Points per image, 2 Points for the category, 10 Points total). For this trivia there is an added element to the puzzle. Step 1 in solving the puzzle is deciphering what the image is. Step 2 requires using the example provided, to figure out the relationship between the clue and the answer, and then apply that relationship to each of the images in step 1.', 18, 'Visual Pun')
;


create table single_slide_multiple_choice_no_answer_bank as (
	select
		id,
		title,
		category,
		game_id,
		has_been_used,
		question_number,
		question_type
	from 
		questions
	where question_type = 'Single Slide Multiple Choice No Answer Bank'
);

alter table single_slide_multiple_choice_no_answer_bank
add column points integer,
add column points_application varchar default 'Each',
add column n_options integer;

update single_slide_multiple_choice_no_answer_bank
	set points = 1, n_options = 4
	where question_number = 1;

update single_slide_multiple_choice_no_answer_bank
	set points = 1, n_options = 4
	where question_number = 3;

update single_slide_multiple_choice_no_answer_bank
	set points = 1, n_options = 4
	where question_number = 5;

update single_slide_multiple_choice_no_answer_bank
	set points = 1, n_options = 4
	where question_number = 7;

update single_slide_multiple_choice_no_answer_bank
	set points = 2, n_options = 2
	where question_number = 10;

update single_slide_multiple_choice_no_answer_bank
	set points = 1, n_options = 4
	where question_number = 11;

update single_slide_multiple_choice_no_answer_bank
	set points = 1, n_options = 4
	where question_number = 12;

update single_slide_multiple_choice_no_answer_bank
	set points = 2, n_options = 4
	where question_number = 13;
				


select * from single_slide_multiple_choice_no_answer_bank ssmcnab ;