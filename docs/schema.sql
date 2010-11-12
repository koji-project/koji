
-- vim:noet:sw=8
-- still needs work
DROP TABLE build_notifications;

DROP TABLE log_messages;

DROP TABLE buildroot_listing;
DROP TABLE imageinfo_listing;

DROP TABLE rpminfo;
DROP TABLE imageinfo;

DROP TABLE group_package_listing;
DROP TABLE group_req_listing;
DROP TABLE group_config;
DROP TABLE groups;

DROP TABLE tag_listing;
DROP TABLE tag_packages;

DROP TABLE buildroot;
DROP TABLE repo;

DROP TABLE build_target_config;
DROP TABLE build_target;

DROP TABLE tag_config;
DROP TABLE tag_inheritance;
DROP TABLE tag;

DROP TABLE build;

DROP TABLE task;

DROP TABLE host_channels;
DROP TABLE host;

DROP TABLE channels;
DROP TABLE package;

DROP TABLE user_groups;
DROP TABLE user_perms;
DROP TABLE permissions;

DROP TABLE sessions;
DROP TABLE users;

DROP TABLE event_labels;
DROP TABLE events;
DROP FUNCTION get_event();
DROP FUNCTION get_event_time(INTEGER);

BEGIN WORK;

-- We use the events table to sequence time
-- in the event that the system clock rolls back, event_ids will retain proper sequencing
CREATE TABLE events (
	id SERIAL NOT NULL PRIMARY KEY,
	time TIMESTAMP NOT NULL DEFAULT NOW()
) WITHOUT OIDS;

-- A function that creates an event and returns the id, used as DEFAULT value for versioned tables
CREATE FUNCTION get_event() RETURNS INTEGER AS '
	INSERT INTO events (time) VALUES (''now'');
	SELECT currval(''events_id_seq'')::INTEGER;
' LANGUAGE SQL;

-- A convenience function for converting events to timestamps, useful for
-- quick queries where you want to avoid JOINs.
CREATE FUNCTION get_event_time(INTEGER) RETURNS TIMESTAMP AS '
	SELECT time FROM events WHERE id=$1;
' LANGUAGE SQL;

-- this table is used to label events
-- most events will be unlabeled, so keeping this separate saves space
CREATE TABLE event_labels (
	event_id INTEGER NOT NULL REFERENCES events(id),
	label VARCHAR(255) UNIQUE NOT NULL
) WITHOUT OIDS;


-- User and session data
CREATE TABLE users (
	id SERIAL NOT NULL PRIMARY KEY,
	name VARCHAR(255) UNIQUE NOT NULL,
	password VARCHAR(255),
	status INTEGER NOT NULL,
	usertype INTEGER NOT NULL,
	krb_principal VARCHAR(255) UNIQUE
) WITHOUT OIDS;

CREATE TABLE permissions (
	id SERIAL NOT NULL PRIMARY KEY,
	name VARCHAR(50) UNIQUE NOT NULL
) WITHOUT OIDS;

-- Some basic perms
INSERT INTO permissions (name) VALUES ('admin');
INSERT INTO permissions (name) VALUES ('build');
INSERT INTO permissions (name) VALUES ('repo');
INSERT INTO permissions (name) VALUES ('livecd');
INSERT INTO permissions (name) VALUES ('maven-import');
INSERT INTO permissions (name) VALUES ('win-import');
INSERT INTO permissions (name) VALUES ('win-admin');
INSERT INTO permissions (name) VALUES ('appliance');

CREATE TABLE user_perms (
	user_id INTEGER NOT NULL REFERENCES users(id),
	perm_id INTEGER NOT NULL REFERENCES permissions(id),
-- versioned - see VERSIONING
	create_event INTEGER NOT NULL REFERENCES events(id) DEFAULT get_event(),
	revoke_event INTEGER REFERENCES events(id),
	creator_id INTEGER NOT NULL REFERENCES users(id),
	revoker_id INTEGER REFERENCES users(id),
	active BOOLEAN DEFAULT 'true' CHECK (active),
	CONSTRAINT active_revoke_sane CHECK (
		(active IS NULL AND revoke_event IS NOT NULL AND revoker_id IS NOT NULL)
		OR (active IS NOT NULL AND revoke_event IS NULL AND revoker_id IS NULL)),
	PRIMARY KEY (create_event, user_id, perm_id),
	UNIQUE (user_id,perm_id,active)
) WITHOUT OIDS;

-- groups are represented as users w/ usertype=2
CREATE TABLE user_groups (
	user_id INTEGER NOT NULL REFERENCES users(id),
	group_id INTEGER NOT NULL REFERENCES users(id),
-- versioned - see VERSIONING
	create_event INTEGER NOT NULL REFERENCES events(id) DEFAULT get_event(),
	revoke_event INTEGER REFERENCES events(id),
	creator_id INTEGER NOT NULL REFERENCES users(id),
	revoker_id INTEGER REFERENCES users(id),
	active BOOLEAN DEFAULT 'true' CHECK (active),
	CONSTRAINT active_revoke_sane CHECK (
		(active IS NULL AND revoke_event IS NOT NULL AND revoker_id IS NOT NULL)
		OR (active IS NOT NULL AND revoke_event IS NULL AND revoker_id IS NULL)),
	PRIMARY KEY (create_event, user_id, group_id),
	UNIQUE (user_id,group_id,active)
) WITHOUT OIDS;

-- a session can create subsessions, which are just new sessions whose
-- 'master' field points back to the session. This field should
-- always point to the top session. If the master session is expired,
-- the all its subsessions should be expired as well.
-- If a session is exclusive, it is the only session allowed for its
-- user. The 'exclusive' field is either NULL or TRUE, never FALSE. This
-- is so exclusivity can be enforced with a unique condition.
CREATE TABLE sessions (
	id SERIAL NOT NULL PRIMARY KEY,
	user_id INTEGER NOT NULL REFERENCES users(id),
	expired BOOLEAN NOT NULL DEFAULT FALSE,
	master INTEGER REFERENCES sessions(id),
	key VARCHAR(255),
	authtype INTEGER,
	hostip VARCHAR(255),
	callnum INTEGER,
	start_time TIMESTAMP NOT NULL DEFAULT NOW(),
	update_time TIMESTAMP NOT NULL DEFAULT NOW(),
	exclusive BOOLEAN CHECK (exclusive),
	CONSTRAINT no_exclusive_subsessions CHECK (
		master IS NULL OR "exclusive" IS NULL),
	CONSTRAINT exclusive_expired_sane CHECK (
		expired IS FALSE OR "exclusive" IS NULL),
	UNIQUE (user_id,exclusive)
) WITHOUT OIDS;
CREATE INDEX sessions_master ON sessions(master);
CREATE INDEX sessions_active_and_recent ON sessions(expired, master, update_time) WHERE (expired IS NOT TRUE AND master IS NULL);

-- Channels are used to limit which tasks are run on which machines.
-- Each task is assigned to a channel and each host 'listens' on one
-- or more channels.  A host will only accept tasks for channels it is
-- listening to.
CREATE TABLE channels (
	id SERIAL NOT NULL PRIMARY KEY,
	name VARCHAR(128) UNIQUE NOT NULL
) WITHOUT OIDS;

-- create default channel
INSERT INTO channels (name) VALUES ('default');
INSERT INTO channels (name) VALUES ('createrepo');
INSERT INTO channels (name) VALUES ('maven');
INSERT INTO channels (name) VALUES ('livecd');
INSERT INTO channels (name) VALUES ('appliance');
INSERT INTO channels (name) VALUES ('vm');

-- Here we track the build machines
-- each host has an entry in the users table also
-- capacity: the hosts weighted task capacity
CREATE TABLE host (
	id SERIAL NOT NULL PRIMARY KEY,
	user_id INTEGER NOT NULL REFERENCES users (id),
	name VARCHAR(128) UNIQUE NOT NULL,
	arches TEXT,
	task_load FLOAT CHECK (NOT task_load < 0) NOT NULL DEFAULT 0.0,
	capacity FLOAT CHECK (capacity > 1) NOT NULL DEFAULT 2.0,
	description TEXT,
	comment TEXT,
	ready BOOLEAN NOT NULL DEFAULT 'false',
	enabled BOOLEAN NOT NULL DEFAULT 'true'
) WITHOUT OIDS;
CREATE INDEX HOST_IS_READY_AND_ENABLED ON host(enabled, ready) WHERE (enabled IS TRUE AND ready IS TRUE);

CREATE TABLE host_channels (
	host_id INTEGER NOT NULL REFERENCES host(id),
	channel_id INTEGER NOT NULL REFERENCES channels(id),
	UNIQUE (host_id,channel_id)
) WITHOUT OIDS;


-- tasks are pretty general and may refer to all sorts of jobs, not
-- just package builds.
-- tasks may spawn subtasks (hence the parent field)
-- top-level tasks have NULL parent
-- the request and result fields are xmlrpc data.
--   this means each task is effectively an xmlrpc call, using this table as
--   the medium.
-- the host_id field indicates which host is running the task. This field
-- is used to lock the task.
-- weight: the weight of the task (vs. host capacity)
-- label: this field is used to label subtasks. top-level tasks will not
--   have a label. some subtasks may be unlabeled. labels are used in task
--   failover to prevent duplication of work.
CREATE TABLE task (
	id SERIAL NOT NULL PRIMARY KEY,
	state INTEGER,
	create_time TIMESTAMP NOT NULL DEFAULT NOW(),
	start_time TIMESTAMP,
	completion_time TIMESTAMP,
	channel_id INTEGER NOT NULL REFERENCES channels(id),
	host_id INTEGER REFERENCES host (id),
	parent INTEGER REFERENCES task (id),
	label VARCHAR(255),
	waiting BOOLEAN,
	awaited BOOLEAN,
	owner INTEGER REFERENCES users(id) NOT NULL,
	method TEXT,
	request TEXT,
	result TEXT,
	eta INTEGER,
	arch VARCHAR(16) NOT NULL,
	priority INTEGER,
	weight FLOAT CHECK (NOT weight < 0) NOT NULL DEFAULT 1.0,
	CONSTRAINT parent_label_sane CHECK (
		parent IS NOT NULL OR label IS NULL),
	UNIQUE (parent,label)
) WITHOUT OIDS;

CREATE INDEX task_by_state ON task (state);
-- CREATE INDEX task_by_parent ON task (parent);   (unique condition creates similar index)
CREATE INDEX task_by_host ON task (host_id);


-- by package, we mean srpm
-- we mean the package in general, not an individual build
CREATE TABLE package (
	id SERIAL NOT NULL PRIMARY KEY,
	name TEXT UNIQUE NOT NULL
) WITHOUT OIDS;

-- CREATE INDEX package_by_name ON package (name);
-- (implicitly created by unique constraint)


-- here we track the built packages
-- this is at the srpm level, since builds are by srpm
-- see rpminfo for isolated packages
-- even though we track epoch, we demand that N-V-R be unique
-- task_id: a reference to the task creating the build, may be
--   null, or may point to a deleted task.
CREATE TABLE build (
	id SERIAL NOT NULL PRIMARY KEY,
	pkg_id INTEGER NOT NULL REFERENCES package (id) DEFERRABLE,
	version TEXT NOT NULL,
	release TEXT NOT NULL,
	epoch INTEGER,
	create_event INTEGER NOT NULL REFERENCES events(id) DEFAULT get_event(),
	completion_time TIMESTAMP,
	state INTEGER NOT NULL,
	task_id INTEGER REFERENCES task (id),
	owner INTEGER NOT NULL REFERENCES users (id),
	CONSTRAINT build_pkg_ver_rel UNIQUE (pkg_id, version, release),
	CONSTRAINT completion_sane CHECK ((state = 0 AND completion_time IS NULL) OR
                                          (state != 0 AND completion_time IS NOT NULL))
) WITHOUT OIDS;

CREATE INDEX build_by_pkg_id ON build (pkg_id);
CREATE INDEX build_completion ON build(completion_time);

-- Note: some of these CREATEs may seem a little out of order. This is done to keep
-- the references sane.

CREATE TABLE tag (
	id SERIAL NOT NULL PRIMARY KEY,
	name VARCHAR(50) UNIQUE NOT NULL
) WITHOUT OIDS;

-- CREATE INDEX tag_by_name ON tag (name);
-- (implicitly created by unique constraint)


-- VERSIONING
-- Several tables are versioned with the following scheme.  Since this
-- is the first, here is the explanation of how it works.
--	The versioning fields are: create_event, revoke_event, and active
--	The active field is either True or NULL, it is never False!
--	The create_event and revoke_event fields refer to the event table
--	A version is active if active is not NULL
--	(an active version also has NULL revoke_event.)
--	A UNIQUE condition can incorporate the 'active' field, making it
--	apply only to the active versions.
--	When a version is made inactive (revoked):
--		revoke_event is set
--		active is set to NULL
--	Query for current data with WHERE active is not NULL
--		(should be same as WHERE revoke_event is NULL)
--	Query for data at event e with WHERE create_event <= e AND e < revoke_event
CREATE TABLE tag_inheritance (
	tag_id INTEGER NOT NULL REFERENCES tag(id),
	parent_id INTEGER NOT NULL REFERENCES tag(id),
	priority INTEGER NOT NULL,
	maxdepth INTEGER,
	intransitive BOOLEAN NOT NULL DEFAULT 'false',
	noconfig BOOLEAN NOT NULL DEFAULT 'false',
	pkg_filter TEXT,
-- versioned - see desc above
	create_event INTEGER NOT NULL REFERENCES events(id) DEFAULT get_event(),
	revoke_event INTEGER REFERENCES events(id),
	creator_id INTEGER NOT NULL REFERENCES users(id),
	revoker_id INTEGER REFERENCES users(id),
	active BOOLEAN DEFAULT 'true' CHECK (active),
	CONSTRAINT active_revoke_sane CHECK (
		(active IS NULL AND revoke_event IS NOT NULL AND revoker_id IS NOT NULL)
		OR (active IS NOT NULL AND revoke_event IS NULL AND revoker_id IS NULL)),
	PRIMARY KEY (create_event, tag_id, priority),
	UNIQUE (tag_id,priority,active),
	UNIQUE (tag_id,parent_id,active)
) WITHOUT OIDS;

CREATE INDEX tag_inheritance_by_parent ON tag_inheritance (parent_id);

-- XXX - need more config options listed here
-- perm_id: the permission that is required to apply the tag. can be NULL
--
CREATE TABLE tag_config (
	tag_id INTEGER NOT NULL REFERENCES tag(id),
	arches TEXT,
	perm_id INTEGER REFERENCES permissions(id),
	locked BOOLEAN NOT NULL DEFAULT 'false',
	maven_support BOOLEAN NOT NULL DEFAULT FALSE,
	maven_include_all BOOLEAN NOT NULL DEFAULT FALSE,
-- versioned - see desc above
	create_event INTEGER NOT NULL REFERENCES events(id) DEFAULT get_event(),
	revoke_event INTEGER REFERENCES events(id),
	creator_id INTEGER NOT NULL REFERENCES users(id),
	revoker_id INTEGER REFERENCES users(id),
	active BOOLEAN DEFAULT 'true' CHECK (active),
	CONSTRAINT active_revoke_sane CHECK (
		(active IS NULL AND revoke_event IS NOT NULL AND revoker_id IS NOT NULL)
		OR (active IS NOT NULL AND revoke_event IS NULL AND revoker_id IS NULL)),
	PRIMARY KEY (create_event, tag_id),
	UNIQUE (tag_id,active)
) WITHOUT OIDS;


-- a build target tells the system where to build the package
-- and how to tag it afterwards.
CREATE TABLE build_target (
	id SERIAL NOT NULL PRIMARY KEY,
	name VARCHAR(50) UNIQUE NOT NULL
) WITHOUT OIDS;


CREATE TABLE build_target_config (
	build_target_id INTEGER NOT NULL REFERENCES build_target(id),
	build_tag INTEGER NOT NULL REFERENCES tag(id),
	dest_tag INTEGER NOT NULL REFERENCES tag(id),
-- versioned - see desc above
	create_event INTEGER NOT NULL REFERENCES events(id) DEFAULT get_event(),
	revoke_event INTEGER REFERENCES events(id),
	creator_id INTEGER NOT NULL REFERENCES users(id),
	revoker_id INTEGER REFERENCES users(id),
	active BOOLEAN DEFAULT 'true' CHECK (active),
	CONSTRAINT active_revoke_sane CHECK (
		(active IS NULL AND revoke_event IS NOT NULL AND revoker_id IS NOT NULL)
		OR (active IS NOT NULL AND revoke_event IS NULL AND revoker_id IS NULL)),
	PRIMARY KEY (create_event, build_target_id),
	UNIQUE (build_target_id,active)
) WITHOUT OIDS;


-- track repos
CREATE TABLE repo (
	id SERIAL NOT NULL PRIMARY KEY,
	create_event INTEGER NOT NULL REFERENCES events(id) DEFAULT get_event(),
	tag_id INTEGER NOT NULL REFERENCES tag(id),
	state INTEGER
) WITHOUT OIDS;

-- external yum repos
create table external_repo (
	id SERIAL NOT NULL PRIMARY KEY,
	name TEXT UNIQUE NOT NULL
);
-- fake repo id for internal stuff (needed for unique index)
INSERT INTO external_repo (id, name) VALUES (0, 'INTERNAL');

create table external_repo_config (
	external_repo_id INTEGER NOT NULL REFERENCES external_repo(id),
	url TEXT NOT NULL,
-- versioned - see earlier description of versioning
	create_event INTEGER NOT NULL REFERENCES events(id) DEFAULT get_event(),
	revoke_event INTEGER REFERENCES events(id),
	creator_id INTEGER NOT NULL REFERENCES users(id),
	revoker_id INTEGER REFERENCES users(id),
	active BOOLEAN DEFAULT 'true' CHECK (active),
	CONSTRAINT active_revoke_sane CHECK (
		(active IS NULL AND revoke_event IS NOT NULL AND revoker_id IS NOT NULL)
		OR (active IS NOT NULL AND revoke_event IS NULL AND revoker_id IS NULL)),
	PRIMARY KEY (create_event, external_repo_id),
	UNIQUE (external_repo_id, active)
) WITHOUT OIDS;

create table tag_external_repos (
	tag_id INTEGER NOT NULL REFERENCES tag(id),
	external_repo_id INTEGER NOT NULL REFERENCES external_repo(id),
	priority INTEGER NOT NULL,
-- versioned - see earlier description of versioning
	create_event INTEGER NOT NULL REFERENCES events(id) DEFAULT get_event(),
	revoke_event INTEGER REFERENCES events(id),
	creator_id INTEGER NOT NULL REFERENCES users(id),
	revoker_id INTEGER REFERENCES users(id),
	active BOOLEAN DEFAULT 'true' CHECK (active),
	CONSTRAINT active_revoke_sane CHECK (
		(active IS NULL AND revoke_event IS NOT NULL AND revoker_id IS NOT NULL)
		OR (active IS NOT NULL AND revoke_event IS NULL AND revoker_id IS NULL)),
	PRIMARY KEY (create_event, tag_id, priority),
	UNIQUE (tag_id, priority, active),
	UNIQUE (tag_id, external_repo_id, active)
);

-- here we track the buildroots on the machines
CREATE TABLE buildroot (
	id SERIAL NOT NULL PRIMARY KEY,
	host_id INTEGER NOT NULL REFERENCES host(id),
	repo_id INTEGER NOT NULL REFERENCES repo (id),
	arch VARCHAR(16) NOT NULL,
	task_id INTEGER NOT NULL REFERENCES task (id),
	create_event INTEGER NOT NULL REFERENCES events(id) DEFAULT get_event(),
	retire_event INTEGER,
	state INTEGER,
	dirtyness INTEGER
) WITHOUT OIDS;

-- track spun images (livecds, installation, VMs...)
CREATE TABLE imageinfo (
	id SERIAL NOT NULL PRIMARY KEY,
        task_id INTEGER NOT NULL REFERENCES task(id),
	filename TEXT NOT NULL,
	filesize BIGINT NOT NULL,
	arch VARCHAR(16) NOT NULL,
	hash TEXT NOT NULL,
	mediatype TEXT NOT NULL
) WITHOUT OIDS;
CREATE INDEX imageinfo_task_id on imageinfo(task_id);

-- this table associates tags with builds.  an entry here tags a package
CREATE TABLE tag_listing (
	build_id INTEGER NOT NULL REFERENCES build (id),
	tag_id INTEGER NOT NULL REFERENCES tag (id),
-- versioned - see earlier description of versioning
	create_event INTEGER NOT NULL REFERENCES events(id) DEFAULT get_event(),
	revoke_event INTEGER REFERENCES events(id),
	creator_id INTEGER NOT NULL REFERENCES users(id),
	revoker_id INTEGER REFERENCES users(id),
	active BOOLEAN DEFAULT 'true' CHECK (active),
	CONSTRAINT active_revoke_sane CHECK (
		(active IS NULL AND revoke_event IS NOT NULL AND revoker_id IS NOT NULL)
		OR (active IS NOT NULL AND revoke_event IS NULL AND revoker_id IS NULL)),
	PRIMARY KEY (create_event, build_id, tag_id),
	UNIQUE (build_id,tag_id,active)
) WITHOUT OIDS;
CREATE INDEX tag_listing_tag_id_key ON tag_listing(tag_id);

-- this is a per-tag list of packages, with some extra info
-- so this allows you to explicitly state which packages belong where
-- (as opposed to beehive where this can only be done at the collection level)
-- these are packages in general, not specific builds.
-- this list limits which builds can be tagged with which tags
-- if blocked is true, then the package is specifically not included. this
--    prevents the package from being included via inheritance
CREATE TABLE tag_packages (
	package_id INTEGER NOT NULL REFERENCES package (id),
	tag_id INTEGER NOT NULL REFERENCES tag (id),
	owner INTEGER NOT NULL REFERENCES users(id),
	blocked BOOLEAN NOT NULL DEFAULT FALSE,
	extra_arches TEXT,
-- versioned - see earlier description of versioning
	create_event INTEGER NOT NULL REFERENCES events(id) DEFAULT get_event(),
	revoke_event INTEGER REFERENCES events(id),
	creator_id INTEGER NOT NULL REFERENCES users(id),
	revoker_id INTEGER REFERENCES users(id),
	active BOOLEAN DEFAULT 'true' CHECK (active),
	CONSTRAINT active_revoke_sane CHECK (
		(active IS NULL AND revoke_event IS NOT NULL AND revoker_id IS NOT NULL)
		OR (active IS NOT NULL AND revoke_event IS NULL AND revoker_id IS NULL)),
	PRIMARY KEY (create_event, package_id, tag_id),
	UNIQUE (package_id,tag_id,active)
) WITHOUT OIDS;

-- package groups (per tag). used for generating comps for the tag repos
CREATE TABLE groups (
	id SERIAL NOT NULL PRIMARY KEY,
	name VARCHAR(50) UNIQUE NOT NULL
        -- corresponds to the id field in a comps group
) WITHOUT OIDS;

-- if blocked is true, then the group is specifically not included. this
--    prevents the group from being included via inheritance
CREATE TABLE group_config (
	group_id INTEGER NOT NULL REFERENCES groups (id),
	tag_id INTEGER NOT NULL REFERENCES tag (id),
	blocked BOOLEAN NOT NULL DEFAULT FALSE,
	exported BOOLEAN DEFAULT TRUE,
	display_name TEXT NOT NULL,
	is_default BOOLEAN,
	uservisible BOOLEAN,
	description TEXT,
	langonly TEXT,
	biarchonly BOOLEAN,
-- versioned - see earlier description of versioning
	create_event INTEGER NOT NULL REFERENCES events(id) DEFAULT get_event(),
	revoke_event INTEGER REFERENCES events(id),
	creator_id INTEGER NOT NULL REFERENCES users(id),
	revoker_id INTEGER REFERENCES users(id),
	active BOOLEAN DEFAULT 'true' CHECK (active),
	CONSTRAINT active_revoke_sane CHECK (
		(active IS NULL AND revoke_event IS NOT NULL AND revoker_id IS NOT NULL)
		OR (active IS NOT NULL AND revoke_event IS NULL AND revoker_id IS NULL)),
	PRIMARY KEY (create_event, group_id, tag_id),
	UNIQUE (group_id,tag_id,active)
) WITHOUT OIDS;

CREATE TABLE group_req_listing (
	group_id INTEGER NOT NULL REFERENCES groups (id),
	tag_id INTEGER NOT NULL REFERENCES tag (id),
	req_id INTEGER NOT NULL REFERENCES groups (id),
	blocked BOOLEAN NOT NULL DEFAULT FALSE,
	type VARCHAR(25),
	is_metapkg BOOLEAN NOT NULL DEFAULT FALSE,
-- versioned - see earlier description of versioning
	create_event INTEGER NOT NULL REFERENCES events(id) DEFAULT get_event(),
	revoke_event INTEGER REFERENCES events(id),
	creator_id INTEGER NOT NULL REFERENCES users(id),
	revoker_id INTEGER REFERENCES users(id),
	active BOOLEAN DEFAULT 'true' CHECK (active),
	CONSTRAINT active_revoke_sane CHECK (
		(active IS NULL AND revoke_event IS NOT NULL AND revoker_id IS NOT NULL)
		OR (active IS NOT NULL AND revoke_event IS NULL AND revoker_id IS NULL)),
	PRIMARY KEY (create_event, group_id, tag_id, req_id),
	UNIQUE (group_id,tag_id,req_id,active)
) WITHOUT OIDS;

-- if blocked is true, then the package is specifically not included. this
--    prevents the package from being included in the group via inheritance
-- package refers to an rpm name, not necessarily an srpm name (so it does
-- not reference the package table).
CREATE TABLE group_package_listing (
	group_id INTEGER NOT NULL REFERENCES groups (id),
	tag_id INTEGER NOT NULL REFERENCES tag (id),
	package TEXT,
	blocked BOOLEAN NOT NULL DEFAULT FALSE,
	type VARCHAR(25) NOT NULL,
	basearchonly BOOLEAN,
	requires TEXT,
-- versioned - see earlier description of versioning
	create_event INTEGER NOT NULL REFERENCES events(id) DEFAULT get_event(),
	revoke_event INTEGER REFERENCES events(id),
	creator_id INTEGER NOT NULL REFERENCES users(id),
	revoker_id INTEGER REFERENCES users(id),
	active BOOLEAN DEFAULT 'true' CHECK (active),
	CONSTRAINT active_revoke_sane CHECK (
		(active IS NULL AND revoke_event IS NOT NULL AND revoker_id IS NOT NULL)
		OR (active IS NOT NULL AND revoke_event IS NULL AND revoker_id IS NULL)),
	PRIMARY KEY (create_event, group_id, tag_id, package),
	UNIQUE (group_id,tag_id,package,active)
) WITHOUT OIDS;

-- rpminfo tracks individual rpms (incl srpms)
-- buildroot_id can be NULL (for externally built packages)
-- even though we track epoch, we demand that N-V-R.A be unique
-- we don't store filename b/c filename should be N-V-R.A.rpm
CREATE TABLE rpminfo (
	id SERIAL NOT NULL PRIMARY KEY,
	build_id INTEGER REFERENCES build (id),
	buildroot_id INTEGER REFERENCES buildroot (id),
	name TEXT NOT NULL,
	version TEXT NOT NULL,
	release TEXT NOT NULL,
	epoch INTEGER,
	arch VARCHAR(16) NOT NULL,
	external_repo_id INTEGER NOT NULL REFERENCES external_repo(id),
	payloadhash TEXT NOT NULL,
	size BIGINT NOT NULL,
	buildtime BIGINT NOT NULL,
	CONSTRAINT rpminfo_unique_nvra UNIQUE (name,version,release,arch,external_repo_id)
) WITHOUT OIDS;
CREATE INDEX rpminfo_build ON rpminfo(build_id);

-- sighash is the checksum of the signature header
CREATE TABLE rpmsigs (
	rpm_id INTEGER NOT NULL REFERENCES rpminfo (id),
	sigkey TEXT NOT NULL,
	sighash TEXT NOT NULL,
	CONSTRAINT rpmsigs_no_resign UNIQUE (rpm_id, sigkey)
) WITHOUT OIDS;

-- buildroot_listing needs to be created after rpminfo so it can reference it
CREATE TABLE buildroot_listing (
	buildroot_id INTEGER NOT NULL REFERENCES buildroot(id),
	rpm_id INTEGER NOT NULL REFERENCES rpminfo(id),
	is_update BOOLEAN NOT NULL DEFAULT FALSE,
	UNIQUE (buildroot_id,rpm_id)
) WITHOUT OIDS;
CREATE INDEX buildroot_listing_rpms ON buildroot_listing(rpm_id);

-- tracks the contents of an image
CREATE TABLE imageinfo_listing (
	image_id INTEGER NOT NULL REFERENCES imageinfo(id),
	rpm_id INTEGER NOT NULL REFERENCES rpminfo(id),
	UNIQUE (image_id, rpm_id)
) WITHOUT OIDS;
CREATE INDEX imageinfo_listing_rpms on imageinfo_listing(rpm_id);

CREATE TABLE log_messages (
    id SERIAL NOT NULL PRIMARY KEY,
    message TEXT NOT NULL,
    message_time TIMESTAMP NOT NULL DEFAULT NOW(),
    logger_name VARCHAR(200) NOT NULL,
    level VARCHAR(10) NOT NULL,
    location VARCHAR(200),
    host VARCHAR(200)
) WITHOUT OIDS;

CREATE TABLE build_notifications (
    id SERIAL NOT NULL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users (id),
    package_id INTEGER REFERENCES package (id),
    tag_id INTEGER REFERENCES tag (id),
    success_only BOOLEAN NOT NULL DEFAULT FALSE,
    email TEXT NOT NULL
) WITHOUT OIDS;

GRANT SELECT ON build, package, task, tag,
tag_listing, tag_config, tag_inheritance, tag_packages,
rpminfo TO PUBLIC;

-- example code to add initial admins
-- insert into users (name, usertype, status, krb_principal) values ('admin', 0, 0, 'admin@EXAMPLE.COM');
-- insert into user_perms (user_id, perm_id)
--       select users.id, permissions.id from users, permissions
--       where users.name in ('admin')
--             and permissions.name = 'admin';

-- Schema additions for multiplatform support

-- we need to track some additional metadata about Maven builds
CREATE TABLE maven_builds (
        build_id INTEGER NOT NULL PRIMARY KEY REFERENCES build(id),
	group_id TEXT NOT NULL,
        artifact_id TEXT NOT NULL,
        version TEXT NOT NULL
) WITHOUT OIDS;

-- Windows-specific build information
CREATE TABLE win_builds (
        build_id INTEGER NOT NULL PRIMARY KEY REFERENCES build(id),
        platform TEXT NOT NULL
) WITHOUT OIDS;

-- Even though we call this archiveinfo, we can probably use it for
-- any filetype output by a build process.  In general they will be
-- archives (.zip, .jar, .tar.gz) but could also be installer executables (.exe)
CREATE TABLE archivetypes (
        id SERIAL NOT NULL PRIMARY KEY,
        name TEXT NOT NULL UNIQUE,
        description TEXT NOT NULL,
        extensions TEXT NOT NULL
) WITHOUT OIDS;

insert into archivetypes (name, description, extensions) values ('jar', 'Jar file', 'jar war rar ear');
insert into archivetypes (name, description, extensions) values ('zip', 'Zip archive', 'zip');
insert into archivetypes (name, description, extensions) values ('pom', 'Maven Project Object Management file', 'pom');
insert into archivetypes (name, description, extensions) values ('tar', 'Tar file', 'tar tar.gz tar.bz2');
insert into archivetypes (name, description, extensions) values ('xml', 'XML file', 'xml');
insert into archivetypes (name, description, extensions) values ('spec', 'RPM spec file', 'spec');
insert into archivetypes (name, description, extensions) values ('exe', 'Windows executable', 'exe');
insert into archivetypes (name, description, extensions) values ('dll', 'Windows dynamic link library', 'dll');
insert into archivetypes (name, description, extensions) values ('lib', 'Windows import library', 'lib');
insert into archivetypes (name, description, extensions) values ('sys', 'Windows device driver', 'sys');
insert into archivetypes (name, description, extensions) values ('inf', 'Windows driver information file', 'inf');
insert into archivetypes (name, description, extensions) values ('cat', 'Windows catalog file', 'cat');
insert into archivetypes (name, description, extensions) values ('msi', 'Windows Installer package', 'msi');
insert into archivetypes (name, description, extensions) values ('pdb', 'Windows debug information', 'pdb');
insert into archivetypes (name, description, extensions) values ('oem', 'Windows driver oem file', 'oem');

-- Do we want to enforce a constraint that a build can only generate one
-- archive with a given name?
CREATE TABLE archiveinfo (
	id SERIAL NOT NULL PRIMARY KEY,
        type_id INTEGER NOT NULL REFERENCES archivetypes (id),
	build_id INTEGER NOT NULL REFERENCES build (id),
	buildroot_id INTEGER REFERENCES buildroot (id),
	filename TEXT NOT NULL,
	size INTEGER NOT NULL,
	md5sum TEXT NOT NULL
) WITHOUT OIDS;
CREATE INDEX archiveinfo_build_idx ON archiveinfo (build_id);
CREATE INDEX archiveinfo_buildroot_idx on archiveinfo (buildroot_id);
CREATE INDEX archiveinfo_type_idx on archiveinfo (type_id);
CREATE INDEX archiveinfo_filename_idx on archiveinfo(filename);

CREATE TABLE maven_archives (
        archive_id INTEGER NOT NULL PRIMARY KEY REFERENCES archiveinfo(id),
	group_id TEXT NOT NULL,
        artifact_id TEXT NOT NULL,
        version TEXT NOT NULL
) WITHOUT OIDS;

CREATE TABLE buildroot_archives (
	buildroot_id INTEGER NOT NULL REFERENCES buildroot (id),
	archive_id INTEGER NOT NULL REFERENCES archiveinfo (id),
	project_dep BOOLEAN NOT NULL,
	PRIMARY KEY (buildroot_id, archive_id)
) WITHOUT OIDS;
CREATE INDEX buildroot_archives_archive_idx ON buildroot_archives (archive_id);

-- Extended information about files built in Windows VMs
CREATE TABLE win_archives (
        archive_id INTEGER NOT NULL PRIMARY KEY REFERENCES archiveinfo(id),
        relpath TEXT NOT NULL,
        platforms TEXT NOT NULL,
        flags TEXT
) WITHOUT OIDS;

COMMIT WORK;
